# soso.event

`soso.event` is a simple event handling library that has a little bit of extra
smarts for async code.

## Quickstart

`$ pip install soso-event`

```python
from soso import event

event = Event("Hello",int)
token = event.connect(print)
event.emit(5)
# outout: 5
token.disconnect()
event.emit(6)
# no output

async def myfunc(event):
    value = await event
    print(value)

asycnio.get_event_loop().create_task(myfunc(event))
event.emit(20)
# output: 20
```

## Motivation

Didn't see anything simple that I could use. `eventkit` was the closest but
seemed a little heavy for my use case.

## Implementation

Straightforward and boring.

