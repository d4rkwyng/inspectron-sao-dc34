# keypad stub — Keys backed by pygame keyboard input via simcore.
#
# Bindings (see simcore.KEYMAP):
#   LEFT  -> key 0 (CH_DOWN, GP12)
#   RIGHT -> key 1 (CH_UP,   GP13)
#   M or DOWN-arrow -> key 2 (MODE, GP14)

from collections import deque

import simcore


class Event:
    def __init__(self, key_number=0, pressed=True, timestamp=0):
        self.key_number = key_number
        self.pressed = pressed
        self.released = not pressed
        self.timestamp = timestamp

    def __repr__(self):
        return ("Event(key_number=%d, %s)"
                % (self.key_number, "pressed" if self.pressed else "released"))

    def __eq__(self, other):
        return (isinstance(other, Event)
                and self.key_number == other.key_number
                and self.pressed == other.pressed)

    def __hash__(self):
        return hash((self.key_number, self.pressed))


class EventQueue:
    def __init__(self):
        self._q = deque()
        self.overflowed = False

    def _push(self, key_number, pressed, timestamp):
        self._q.append(Event(key_number, pressed, timestamp))

    def get(self):
        simcore.pump()          # translate pending pygame input first
        if self._q:
            return self._q.popleft()
        return None

    def get_into(self, event):
        e = self.get()
        if e is None:
            return False
        event.key_number = e.key_number
        event.pressed = e.pressed
        event.released = e.released
        event.timestamp = e.timestamp
        return True

    def clear(self):
        self._q.clear()
        self.overflowed = False

    def __bool__(self):
        return bool(self._q)

    def __len__(self):
        return len(self._q)


class Keys:
    def __init__(self, pins, *, value_when_pressed, pull=True,
                 interval=0.02, max_events=64):
        self._pins = tuple(pins)
        self.events = EventQueue()
        simcore.register_key_queue(self.events)
        simcore.log("keypad: %s (LEFT/RIGHT = CH-/CH+, M or DOWN = MODE)"
                    % ", ".join(p.name for p in self._pins))

    @property
    def key_count(self):
        return len(self._pins)

    def reset(self):
        self.events.clear()

    def deinit(self):
        pass
