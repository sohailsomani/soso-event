import asyncio
import collections
import enum
import logging
import typing
import weakref


class EventToken:
    def __init__(self, value: typing.Any, event: "Event"):
        self.event: typing.Optional[
            weakref.ReferenceType["Event"]] = weakref.ref(event)
        self.value = value

    def disconnect(self) -> None:
        if self.event is None:
            return
        event = self.event()
        if event is None:
            return
        event.disconnectToken(self)
        self.event = None

    def __del__(self) -> None:
        self.disconnect()

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, EventToken) and self.value == other.value


class Event:
    class Group(enum.Enum):
        STORE = 1
        PROCESS = 2

    def __init__(self, name: str, *argTypes: type, **kwArgTypes: type):
        self._name = name
        self._loop = asyncio.get_event_loop()
        self._argTypes = argTypes
        self._kwArgTypes = kwArgTypes
        self._groups: typing.Dict[
            Event.Group,
            typing.List[EventToken]] = collections.defaultdict(list)
        self._nextEventToken: int = 0
        self._tokenMap: typing.Dict[EventToken,
                                    typing.Tuple[typing.Callable[[typing.Any],
                                                                 typing.Any],
                                                 Event.Group]] = dict()
        self._onDisconnect: typing.Optional[typing.Callable[["Event"],
                                                            None]] = None
        self._nerrors = 0
        self._logger = logging.getLogger(__name__)
        self.__isBeingEmitted = False

    def __len__(self) -> int:
        return len(self._tokenMap)

    @property
    def name(self) -> str:
        return self._name

    def getHandlers(
            self) -> typing.List[typing.Callable[[typing.Any], typing.Any]]:
        return [
            self._tokenMap[token][0]
            for token in self._groups[Event.Group.STORE] +
            self._groups[Event.Group.PROCESS]
        ]

    def callHandler(self, f: typing.Callable[..., typing.Any], *a: typing.Any,
                    **kw: typing.Any) -> None:
        # self._logger.debug("Calling %s",f)
        if self.__isBeingEmitted:
            return  # avoid recursion
        self.__isBeingEmitted = True
        try:
            ret = f(*a, **kw)
            try:
                self._loop.create_task(ret)
            except TypeError:
                # HACK: in the case that we didn't actually get an awaitable
                pass
            self._nerrors = 0
        except Exception as e:
            self._nerrors += 1
            import traceback
            self._logger.error("Error calling %s: %s", f, str(e))
            self._logger.debug("Error calling %s(*%s,**%s): %s", f, a, kw,
                               str(e))
            if self._nerrors == 1:
                self._logger.error(traceback.format_exc())
            else:
                self._logger.debug(traceback.format_exc())
        finally:
            self.__isBeingEmitted = False

    def __call__(self, *a, **kw) -> None:  # type: ignore
        self._logger.debug("Emitting %s", self)
        # self._logger.debug("Emitting %s(%s,%s)",self,a,kw)
        self._validateArgs(a, kw)
        for f in self.getHandlers():
            self.callHandler(f, *a, **kw)

    def __await__(self) -> typing.Generator[typing.Any, None, typing.Any]:
        def callback(*args: typing.Any) -> None:
            if not fut.done():
                fut.set_result(args[0] if len(args) == 1 else args)

        fut: asyncio.Future[typing.Any] = asyncio.Future()
        token = self.connect(callback, Event.Group.PROCESS)
        fut.add_done_callback(lambda f: token.disconnect())
        return fut.__await__()

    def _validateArgs(self, args: typing.Iterable[typing.Any],
                      kwargs: typing.Mapping[str, typing.Any]) -> None:
        pass

    def emit(self, *a: typing.Any, **kw: typing.Any) -> None:
        self(*a, **kw)

    def connect(self, callback: typing.Callable[..., typing.Any],
                group: Group) -> EventToken:
        for token, (cb, grp) in self._tokenMap.items():
            if callback == cb:
                return token
        self._logger.debug("Connecting %s to %s", self, callback)
        token = self._newEventToken()
        self._tokenMap[token] = (callback, group)
        self._groups[group].append(token)
        return token

    def onDisconnect(self, callback: typing.Callable[["Event"], None]) -> None:
        self._onDisconnect = callback

    def _newEventToken(self) -> EventToken:
        self._nextEventToken += 1
        return EventToken(self._nextEventToken, self)

    def disconnectToken(self, token: EventToken) -> None:
        if token not in self._tokenMap:
            return
        _, group = self._tokenMap[token]
        del self._tokenMap[token]
        self._logger.debug("Disconnecting %s token: %s", self, token)
        self._groups[group] = [a for a in self._groups[group] if a != token]
        if self._onDisconnect is not None:
            self._onDisconnect(self)

    def __del__(self) -> None:
        items = list(self._tokenMap.items())
        for token, group in items:
            self.disconnectToken(token)

    @property
    def count(self) -> int:
        return sum([len(g) for g in self._groups.values()])

    def __repr__(self) -> str:
        return f'#<Event {self._name} numListeners={self.count}>'
