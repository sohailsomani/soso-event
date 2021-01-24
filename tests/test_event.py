import asyncio
import unittest
from unittest import mock

from soso.event import Event


class TestEvent(unittest.TestCase):
    def test_KeywordArgument(self) -> None:
        event = Event("Test", arg1=int, arg2=float)
        cb = mock.Mock()
        event.connect(cb, Event.Group.PROCESS)
        event(arg2=1.1, arg1=1)
        cb.assert_called_with(arg1=1, arg2=1.1)

    def test_KeywordArgument2(self) -> None:
        event = Event("Test", arg1=int, arg2=float)
        cb = mock.Mock()
        event.connect(cb, Event.Group.PROCESS)
        event(1, 1.1)
        cb.assert_called_with(1, 1.1)

    def test_len(self) -> None:
        event = Event("Test")
        self.assertEqual(len(event), 0)
        cb = mock.Mock()
        token = event.connect(cb, Event.Group.PROCESS)
        self.assertEqual(len(event), 1)
        token.disconnect()
        self.assertEqual(len(event), 0)

    async def asyncFunc(self) -> None:
        self.called = True

    def test_lambdaReturningAsync(self) -> None:
        event = Event("Test")
        event.connect(lambda: self.asyncFunc(), Event.Group.STORE)
        event.emit()
        self.called = False
        asyncio.get_event_loop().stop()
        asyncio.get_event_loop().run_forever()
        self.assertTrue(self.called)

    def test_avoidingRecursion(self) -> None:
        event = Event("Test")
        event.connect(event.emit, Event.Group.STORE)
        event.emit()

    async def waitForEvent(self, event: Event) -> None:
        await event
        self.called = True
        asyncio.get_event_loop().stop()

    def test_awaitable(self) -> None:
        event = Event("Test")
        self.called = False

        asyncio.get_event_loop().create_task(self.waitForEvent(event))
        asyncio.get_event_loop().call_soon(event.emit)
        asyncio.get_event_loop().run_forever()

        self.assertTrue(self.called)
