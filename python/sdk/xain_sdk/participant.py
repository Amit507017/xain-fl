import sys
from abc import ABC, abstractmethod
from copy import deepcopy
import enum
import json
import logging
import pickle
import threading
import time
from typing import Any, Dict, List, Tuple, TypeVar, cast
import uuid

import numpy as np
from numpy import ndarray
from requests.exceptions import ConnectionError

from .http import AggregatorClient, AnonymousCoordinatorClient, CoordinatorClient
from .interfaces import TrainingResultABC, TrainingInputABC

LOG = logging.getLogger("http")



class Participant(ABC):
    def __init__(self) -> None:
        super(Participant, self).__init__()

    @abstractmethod
    def init_weights(self) -> TrainingResultABC:
        raise NotImplementedError()

    @abstractmethod
    def train_round(self, training_input: TrainingInputABC) -> TrainingResultABC:
        raise NotImplementedError()


class State(enum.Enum):
    WAITING = 1
    TRAINING = 2
    DONE = 3


class StateRecord:
    def __init__(self, state: State = State.WAITING, round: int = -1) -> None:
        # By default, a re-entrant lock is used but we want a normal
        # lock here
        self.cond: threading.Condition = threading.Condition(threading.Lock())
        self.locked: bool = False
        self.round: int = round
        self.state: State = state
        self.dirty: bool = False

    def __enter__(self):
        self.cond.acquire()
        self.locked = True
        return self

    def __exit__(self, *args, **kwargs):
        if self.dirty:
            self.cond.notify()
            self.dirty = False
        self.locked = False
        self.cond.release()

    def assert_locked(self):
        if not self.locked:
            raise RuntimeError("StateRecord must be locked")

    def lookup(self) -> Tuple[State, int]:
        self.assert_locked()
        return self.state, self.round

    def set_state(self, state: State) -> None:
        self.assert_locked()
        self.state = state
        self.dirty = True

    def set_round(self, round: int) -> None:
        self.assert_locked()
        self.round = round
        self.dirty = True

    def wait_until_selected_or_done(self) -> State:
        self.assert_locked()
        # wait() releases the lock. It's fine to set the `locked`
        # attribute, because until wait() runs, the lock won't be
        # released so no other thread will try to access this attribute.
        #
        # It's also fine to re-set the attribute to True afterward,
        # because this thread will hold the lock at this point.
        #
        # FIXME: explain better why this it is safe
        self.locked = False
        self.cond.wait_for(lambda: self.state in {State.TRAINING, State.DONE})
        self.locked = True
        return self.state


class InternalParticipant:
    def __init__(self, coordinator_url: str, participant: Participant):
        self.state_record = StateRecord()
        self.participant = participant

        self.anonymous_client = AnonymousCoordinatorClient(coordinator_url)
        self.coordinator_client = None
        self.aggregator_client = None

        self.exit_event = threading.Event()
        self.heartbeat_thread = None

    def run(self):
        self.rendez_vous()
        while True:
            with self.state_record:
                self.state_record.wait_until_selected_or_done()
                state, _ = self.state_record.lookup()

            if state == State.DONE:
                return

            if state == State.TRAINING:
                self.aggregator_client = self.coordinator_client.start_training()
                training_input = self.aggregator_client.download()

                if training_input.is_initialization_round():
                    result = self.participant.init_weights()
                else:
                    result = self.participant.train_round(training_input)
                    assert isinstance(result, TrainingResultABC)

                self.aggregator_client.upload(result)

                with self.state_record:
                    self.state_record.set_state(State.WAITING)

    def rendez_vous(self):
        try:
            self.coordinator_client = self.anonymous_client.rendez_vous()
        except ConnectionError as err:
            LOG.error("rendez vous failed: %s", err)
            raise ParticipantError("Rendez-vous request failed")
        except InterruptedError:
            LOG.warning("exiting: interrupt signal caught")
            sys.exit(0)

        self.start_heartbeat()

    def start_heartbeat(self):
        self.heartbeat_thread = HeartBeatWorker(
            deepcopy(self.coordinator_client), self.state_record, self.exit_event
        )
        self.heartbeat_thread.start()


class HeartBeatWorker(threading.Thread):
    def __init__(
        self,
        coordinator_client: CoordinatorClient,
        state_record: StateRecord,
        exit_event: threading.Event,
    ):
        self.coordinator_client = coordinator_client
        self.state_record = state_record
        self.exit_event = exit_event
        super(HeartBeatWorker, self).__init__(daemon=True)

    def run(self):
        LOG.debug("heartbeat thread starting")
        try:
            while True:
                self.heartbeat()
                if self.exit_event.wait(timeout=5):
                    LOG.debug("heartbeat worker exiting: exit flag set in main thead")
                    return
        except:
            LOG.exception("error while sending heartbeat, exiting")
            self.exit_event.set()
            return

    def heartbeat(self):
        resp = self.coordinator_client.heartbeat()

        with self.state_record as state_record:
            current_state, current_round = state_record.lookup()
            state = resp["state"]

            # FIXME: The API should return proper JSON that would
            # make this much cleaner
            if state == "stand_by" and current_state != State.WAITING:
                state_record.set_state(State.STAND_BY)

            elif state == "finish" and current_state != State.DONE:
                state_record.set_state(State.DONE)

            elif state == "reject":
                state_record.set_state(State.DONE)

            elif state == "round":
                round = resp["round"]
                if current_state != State.TRAINING:
                    state_record.set_state(State.TRAINING)
                if current_round != round:
                    state_record.set_round(round)


class ParticipantError(Exception):
    pass
