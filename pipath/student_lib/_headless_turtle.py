"""A stand-in for the turtle module when there is no screen (tests, or a Pi with no desktop).

The shim puts it in place of `turtle` only when no display is available, so turtle programs still
run to the end (drawing nothing) instead of crashing with "no display name". On the desktop the
real turtle module is used.
"""


class Terminator(Exception):
    """Raised by the real turtle when its window is closed."""


class _Thing:
    """Accepts any turtle or screen method and does nothing (positions are still tracked)."""

    def __init__(self, *a, **kw):
        self._x = self._y = 0.0
        self._heading = 0.0

    def __getattr__(self, name):
        return lambda *a, **kw: None

    # a few methods programs read values from
    def position(self):
        return (round(self._x, 2) + 0.0, round(self._y, 2) + 0.0)

    pos = position

    def heading(self):
        return self._heading

    def xcor(self):
        return self._x

    def ycor(self):
        return self._y

    def forward(self, d):
        import math
        self._x += d * math.cos(math.radians(self._heading))
        self._y += d * math.sin(math.radians(self._heading))

    fd = forward

    def backward(self, d):
        self.forward(-d)

    bk = back = backward

    def left(self, a):
        self._heading = (self._heading + a) % 360

    lt = left

    def right(self, a):
        self.left(-a)

    rt = right

    def goto(self, x, y=None):
        if y is None:
            x, y = x
        self._x, self._y = x, y

    setpos = setposition = goto

    def window_width(self):
        return 800

    def window_height(self):
        return 600


Turtle = RawTurtle = Pen = _Thing
_screen = _Thing()
_turtle = _Thing()


def Screen():
    return _screen


def done():
    pass


mainloop = exitonclick = bye = done


def __getattr__(name):
    """turtle.forward(100) and friends: the module-level functions drive one default turtle."""
    return getattr(_turtle, name)
