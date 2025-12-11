---
title: "Crimes Against Pythonkind"
date: "2025-12-09"
excerpt: "Heinous, horrifying, disgusting, and downright weird hacks in CPython."
tags: ["rev", "pwn", "python"]
---

> For future reference: Everything in this post will be run with the latest version of CPython 3.14 available from `uv`:
> `Python 3.14.0a5 (main, Mar 11 2025, 17:29:28) [Clang 20.1.0 ] on linux`
>
> This may or may not work on other Python interpreters, and your best bet is getting it to work on PyPy or the like, but it will most likely break catastrophically on you in fun and unpredictable ways.

## Introduction: `id` and `ctypes` and caching, oh my

In order to fully understand what heinous, despicable acts of Python fuckery I commit in this post, first you need to understand a few of the more hidden aspects of Python as a language.

### `id()`

First is the `id` builtin. This is a globally available function that is described by the CPython docs as:

> Return the “identity” of an object. This is an integer which is guaranteed to be unique and constant for this object during its lifetime. Two objects with non-overlapping lifetimes may have the same id() value.
>
> CPython implementation detail: This is the address of the object in memory.

This seems pretty bog-standard at first glance - it lets you know where an object is in memory so you can test if two objects are the same - at a memory level, not an equivalency level. However, the fact that it returns the absolute address in memory of any object you give it in CPython becomes incredible powerful when we begin to combine it with another stdlib module, `ctypes`.

### `ctypes`

ctypes is described by the docs as:

> ctypes is a foreign function library for Python. It provides C compatible data types, and allows calling functions in DLLs or shared libraries. It can be used to wrap these libraries in pure Python.

This is basically just a fancy way to say that it allows our Python code to more closely poke at the underlying C runtime that powers CPython. Most critically, though, is the ability to use `ctypes.POINTER` and `ctypes.Structure`. `Structure` actually provides a metaclass that allows us to define C-style structs from Python, like this code example:

```py
>>> from ctypes import *

>>> class POINT(Structure):
...     _fields_ = [("x", c_int),
...                 ("y", c_int)]
... 

>>> point = POINT(10, 20)

>>> print(point.x, point.y)
10 20

>>> point = POINT(y=5)

>>> print(point.x, point.y)
0 5

>>> POINT(1, 2, 3)
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
TypeError: too many initializers
```

This is great for embedding native library calls, wrapping DLLs, and a whole bunch of other legitimate uses. But that's not what we're after here. Thankfully though, we can define pointers to any standard C type with just a memory address as an `int` with code like this:

```py
ptr = ctypes.cast(0x1234567890, ctypes.POINTER(ctypes.c_uint))
```

In C, this would be:

```c
int *ptr = (int *)0x1234567890;
```

Awesome! But what can we use this for? This feels pointless unless we can get a pointer to something interesting... but wait, remember `id()`?

> CPython implementation detail: This is ***the address of the object in memory***.

Oh yes... but now we need a target. What could we possibly poke at in memory that would stay completely constant for Python's runtime? Well... how about...

### The `int` Cache

Let's start with a question. What numbers do you think are used the most often? Likely you'd say `1` to `256`, or `1` to `512`, or maybe even `1` to `1024`, if you're feeling liberal. In fact, if you agreed with the last of those three, you'd be very close to the Python developers - they decided that the optimal range of numbers that are used the most often are `-5` to `1024`:

```c
#define _PY_NSMALLPOSINTS           1025
#define _PY_NSMALLNEGINTS           5
```

([source](https://github.com/python/cpython/blob/09d6bf20b67f4d3001afac9d20886a6e9cbcc94f/Include/internal/pycore_runtime_structs.h#L109-L110), `cpython/Include/internal/pycore_runtime_structs.h`)

So, when the CPython interpreter starts up, it makes a bunch of what you know as `int` objects. Since `int` is a builtin type and is immutable, these don't ever change and just sit in their respective spots in memory. In fact, we can even see this in action by examining the `id` of various ints:

```python
>>> y = 1; x = 1;

>>> id(y), id(x)
(139980780403984, 139980780403984)

>>> y = 99999; x = 99999;

>>> id(y), id(x)
(139980508314704, 139980508311120)
```

(Note the above code snippet might not work on your CPython since it's dependent on the interpret-time optimizations. If it doesn't work in your normal `python` REPL, try IPython.)

Now that we understand these basics, let's jump into our first crime against Pythonkind:

## 1. `144 == 143`, duh

In your CPython interpreter, go ahead and run:

```py
>>> 144 == 143
```

Clearly, this outputs `False`. Right?

Well...

```py
>>> 144 == 143
False
```

Yeah, obviously it does! We haven't fucked anything up that much *yet*.

But remember how the range of cached numbers in Python 3.14 goes up to 1024? Both of those numbers fit in that range! This means that no matter what you do, `id(143)` will ALWAYS point to the same point in memory, so long as CPython isn't re-initialized. Do you see where I'm going with this yet?

Let's first crack open any debugger of choice and launch a Python REPL with it. With `gdb`, you can do:

```bash
$ gdb --args python
GNU gdb (Fedora Linux) 16.3-6.fc43
Copyright (C) 2024 Free Software Foundation, Inc...
```

Then, enter `run` in the GDB shell and run your Python!

```gdb
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib64/libthread_db.so.1".
Python 3.14.0a5 (main, Mar 11 2025, 17:29:28) [Clang 20.1.0 ] on linux
Type "help", "copyright", "credits" or "license" for more information.
Ctrl click to launch VS Code Native REPL
>>> x = 143
>>> hex(id(x))
'0x7ffff7d098e8'
```

Then, you can press `Ctrl+C` to drop back to the GDB shell:

```gdb
Program received signal SIGINT, Interrupt.
0x00007ffff647ac5e in __internal_syscall_cancel () from /lib64/libc.so.6
(gdb) 
```

And we can poke the memory!

```gdb
(gdb) x/4gx 0x7ffff7d098e8
0x7ffff7d098e8 <_PyRuntime+18648>:      0x00000080c0000000      0x00007ffff7ca5e00
0x7ffff7d098f8 <_PyRuntime+18664>:      0x000000000000000c      0x000000000000008f
```

So what are we looking at here? Well, there's 4 core parts to a `PyLong` (the internal C API name for an `int`). They're quite well-defined by the comments in the CPython source, so I'll just cite it directly:

```c
/* Long integer representation.

   Long integers are made up of a number of 30- or 15-bit digits, depending on
   the platform. The number of digits (ndigits) is stored in the high bits of
   the lv_tag field (lvtag >> _PyLong_NON_SIZE_BITS).

   The absolute value of a number is equal to
        SUM(for i=0 through ndigits-1) ob_digit[i] * 2**(PyLong_SHIFT*i)

   The sign of the value is stored in the lower 2 bits of lv_tag.

    - 0: Positive
    - 1: Zero
    - 2: Negative

   The third lowest bit of lv_tag is
   set to 1 for the small ints.

   In a normalized number, ob_digit[ndigits-1] (the most significant
   digit) is never zero.  Also, in all cases, for all valid i,
        0 <= ob_digit[i] <= PyLong_MASK.

   The allocation function takes care of allocating extra memory
   so that ob_digit[0] ... ob_digit[ndigits-1] are actually available.
   We always allocate memory for at least one digit, so accessing ob_digit[0]
   is always safe. However, in the case ndigits == 0, the contents of
   ob_digit[0] may be undefined.
*/

typedef struct _PyLongValue {
    uintptr_t lv_tag; /* Number of digits, sign and flags */
    digit ob_digit[1];
} _PyLongValue;

struct _longobject {
    PyObject_HEAD
    _PyLongValue long_value;
};
```

([source](https://github.com/python/cpython/blob/09d6bf20b67f4d3001afac9d20886a6e9cbcc94f/Include/cpython/longintrepr.h#L64-L101), `cpython/Include/cpython/longintrepr.h`)

This might seem like an obtuse way to store integers to begin with, but it functions, and for our purposes (with numbers small enough to fit in one `digit`), it's easier than you'd think to decode. We also know how PyObject_HEAD is defined for `VarObject`s, which is what `PyLong` is:

```c
struct PyObject {
    le ssize_t ob_refcnt;    // 8 bytes
    void *ob_type;           // 8 bytes
    ssize_t ob_size;         // 8 bytes
};
```

And so, putting it all together, we can see the four values we just got all defined:

- The number of references to this object (`0x00000080c0000000`)
- The pointer to the type of this object (`0x00007ffff7ca5e00`)
- The size of this object (`0x000000000000000c`)
- The first digit of the `PyLong`, containing the value (`0x000000000000008f`)

Only one of these is a pointer, so we can decode these to get some interesting data. All we need to do is switch a single character out in the GDB command:

```gdb
(gdb) x/4gu 0x7ffff7d098e8
0x7ffff7d098e8 <_PyRuntime+18648>:      552977039360    140737350622720
0x7ffff7d098f8 <_PyRuntime+18664>:      12      143
```

Wait, what's that? The 4th field, `ob_digits[0]`, is our value that we started with - `143`!

At first glance, there are also a shit ton of references to this object (552977039360, whoa!). But this is, in fact, an inaccurate number, and instead is a mere 49280, when decoded little endian as intended.

Now we can read this from memory with GDB, but what if we wanted to do this without having to hook Python up to a debugger? Well, with the power of `ctypes.Structure`, we can actually define a `PyLong` on the Python side as an object:

```py
import ctypes

class PyLongObject(ctypes.Structure):
    _fields_ = [
        ('ob_refcnt', ctypes.c_ssize_t),
        ('ob_type', ctypes.c_void_p),
        ('ob_size', ctypes.c_ssize_t),
        ('ob_digit', ctypes.c_uint * 1)
    ]
```

Now, let's try that again, but without GDB. In any old CPython REPL, we can run:

```python
>>> import ctypes
>>> class PyLongObject(ctypes.Structure):
...     _fields_ = [
...         ('ob_refcnt', ctypes.c_ssize_t),
...         ('ob_type', ctypes.c_void_p),
...         ('ob_size', ctypes.c_ssize_t),
...         ('ob_digit', ctypes.c_uint * 1)
...     ]
... 
>>> id(143)
139731831658728
>>> ptr = ctypes.cast(id(143), ctypes.POINTER(PyLongObject))
>>> ptr.contents.ob_digit
<__main__.c_uint_Array_1 object at 0x7f15ca72f790>
>>> ptr.contents.ob_digit[0]
143
```

Now, we can read the memory *within* Python, without external debuggers... but... could we **write** the memory?

```python
>>> ptr.contents.ob_digit[0] = 144
```

Hm. No errors... let's read it again to make sure that it's written...

```python
>>> ptr.contents.ob_digit[0]
144
```

Yeah, that's right. So... what if...

```python
>>> 143
144
```

Uh oh! We definitely fucked something up. Now, answering the title of this section...

```python
>>> 144 == 143
True
```

It works! Finally, we can recreate this entire effect with one snippet of Python...

```python
import ctypes

class PyLongObject(ctypes.Structure):
    _fields_ = [
        ('ob_refcnt', ctypes.c_ssize_t),
        ('ob_type', ctypes.c_void_p),
        ('ob_size', ctypes.c_ssize_t),
        ('ob_digit', ctypes.c_uint * 1)
    ]

ptr = ctypes.cast(id(143), ctypes.POINTER(PyLongObject))
ptr.contents.ob_digit[0] = 144

print(144 == 143)
```

This should consistently print `True` and no other output.

## 2. Schrödinger's Hashmap

Integers are fun, but strings are the backbone of Python. Variable names and dictionary keys (and attributes, [because of `__dict__`](https://coderivers.org/blog/python-__dict__/)) are all strings. Like integers, strings are meant to be immutable. Like integers, we can lie about that by poking the memory.

When you hash a string (`hash("hello")`), Python calculates the value and stores it inside the struct so it never has to calculate it again. If we modify the string in memory after the hash is calculated, the string changes, but the hash remains. This creates a ghost object that is equal to its new value, but lives in the wrong "bucket" inside dictionaries.

This time around, I'll skip the boring stuff of poking manually at memory - strings in Python are stored roughly like this:

```py
import ctypes

class PyASCIIObject(ctypes.Structure):
    _fields_ = [
        ('ob_refcnt', ctypes.c_ssize_t), # again, the common PyObject_HEAD
        ('ob_type', ctypes.c_void_p),
        ('length', ctypes.c_ssize_t),
        ('hash', ctypes.c_ssize_t), # <- what we want to mess with
        ('state', ctypes.c_int),
        ('wstr', ctypes.c_void_p)
        # char data follows...
    ]
```

By getting an address of a string, you can modify these values that are meant to be immutable! For instance, we can make `hash()` lie pretty easily. Let's say we want to make the hash of `evil_string` match the hash of `string`.

```py
>>> evil_string = "hello, evil world!!!"
>>> string = "hello, world!"
>>> hash(evil_string), hash(string), hash(evil_string) == hash(string)
(-569253570518681530, 8645023704131673044, False)
>>> ptr = ctypes.cast(id(evil_string), ctypes.POINTER(PyASCIIObject))
>>> ptr.contents.hash
-569253570518681530
>>> ptr.contents.hash = hash(string)
>>> hash(evil_string), hash(string), hash(evil_string) == hash(string)
(8645023704131673044, 8645023704131673044, True)
```

But what if...

```py
>>> evil_string == string
False
```

Aw man, nothing. So what's the point of doing all that, anyway? Well, we can make dicts that lie! Let's say we want to change this key from `'test'` to not work while still making `keys()` return `['test']`.

```py
>>> key = 'test'
>>> x = {key: 12345}
```

Well, we can cast `'test'` to a pointer and change its hash to something else...

```py
>>> ptr = ctypes.cast(id(key), ctypes.POINTER(PyASCIIObject))
>>> ptr.contents.hash = -2 # hash of -1, don't ask ;)
```

And just like that, we've fucked up this dict!

```py
>>> x
{'test': 12345}
```

Well, looks normal. Let's try to get the value!

```py
>>> x['test']
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    x['test']
    ~^^^^^^^^
KeyError: 'test'
```

Uh oh! Can we do...

```py
>>> x.keys()
dict_keys(['test'])
```

Yep, that's also normal! We can even get `x.values()` successfully, but yet, no matter how hard we try:

```py
>>> x[list(x.keys())[0]]
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    x[list(x.keys())[0]]
    ~^^^^^^^^^^^^^^^^^^^
KeyError: 'test'
```

This is all because `keys()` just iterates over the raw list of pointers stored in the dictionary. It doesn't check hashes. `__getitem__` (lookup) runs the hash. That's why one works and the other fails.

Finally, now that we can apply this to a dict...

### Introducing... `__dict__`

Whenever you get an attribute or method of an instance of an object in most strictly typed languages, it usually relies on some sort of virtual method table lookup (read [the Wikipedia page on it](https://en.wikipedia.org/wiki/Virtual_method_table) for more information). For instance, let's take:

```py
class Example:
    attr1: int
    attr2: int

    def __init__(self):
        self.attr1 = 1
        self.attr2 = 2
```

In Python, we can assign to any attribute name on an object, even if it doesn't exist in the class. For example:

```py
>>> obj.attr3
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    obj.attr3
AttributeError: 'Example' object has no attribute 'attr3'. Did you mean: 'attr1'?
>>> obj.attr3 = 'test'
>>> obj.attr3
'test'
```

This is *valid Python*! Of course, type checkers won't like it at all, but that's okay. Because, in fact, attributes aren't stored in some fixed storage - Python uses its own `dict` hashmap type to internally store attributes of objects, and we can get a handle on it with `object.__dict__`. Let's see what's defined!

```py
>>> obj.__dict__
{'attr1': 1, 'attr2': 2, 'attr3': 'test'}
```

Look at that - all the defined attributes of the object, even the one that wasn't defined with the class. But if this is all driven by a `dict`, which we were able to corrupt and mess with before...

### `__dict__` Corruption

Let's start by making a new instance of `Example` that's still unpolluted. We can quickly verify that it's correct by checking `__dict__`:

```py
>>> obj = Example()
>>> obj.__dict__
{'attr1': 1, 'attr2': 2}
```

Everything is correct, and you can get `attr1` like so:

```py
>>> obj.attr1
1
```

Let's make it inaccessible!

```py
>>> key = list(obj.__dict__.keys())[0] # this guarantees we have 'attr1' at the same address
>>> ptr = ctypes.cast(id(key), ctypes.POINTER(PyASCIIObject))
>>> ptr.contents.hash = -2
>>> obj.attr1
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    obj.attr1
AttributeError: 'Example' object has no attribute 'attr1'. Did you mean: 'attr2'?
>>> obj.attr2
2
>>> obj.__dict__
{'attr1': 1, 'attr2': 2}
```

We can try other methods of accessing the attributes too - like [the `dir` builtin](https://docs.python.org/3/library/functions.html#dir) and `__getattribute__`:

```py
>>> dir(obj)
[..., 'attr1', 'attr2']           # it's definitely fooled!
>>> obj.__getattribute__('attr1') # but we can't access it, no matter how hard we try
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    obj.__getattribute__('attr1')
    ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^
AttributeError: 'Example' object has no attribute 'attr1'. Did you mean: 'attr2'?
```

Obviously, this can be countered by using `__slots__` to fix the attributes, as outlined in [this Python wiki page](https://wiki.python.org/moin/UsingSlots), but most modern Python code still uses `__dict__` in the end, and that means we can fuck it up a good deal with this technique.

## 3. The Pychurian Candidate

One of my favorite tricks to pull out to impress people with Python is `__code__`. If you define a function, you can use its `__code__` attribute to get the underlying Python bytecode that's run by the interpreter. With the `inspect` stdlib module, you can even get the current function's bytecode.

By also using the stdlib `dis` module, we can disassemble the Python bytecode generated for any function we want, on the fly! For instance:

```py
>>> import dis
>>> def hello():
...     print("Hello, world!")
>>> hello.__code__
<code object hello at 0x7fe3a5d217a0, file "<stdin>-1", line 1>
>>> hello.__code__.co_code
b'\x95\x00X\x01\x00\x00\x00\x00\x00\x00\x00\x00P\x003\x01\x00\x00\x00\x00\x00\x00\x1f\x00P\x01#\x00'
>>> dis.dis(hello.__code__.co_code)
          RESUME                   0
          LOAD_GLOBAL              1
          LOAD_CONST               0
          CALL                     1
          POP_TOP
          LOAD_CONST               1
          RETURN_VALUE
```

Now, you can see both see the bytes of the raw Python bytecode generated, and disassemble it with `dis` for a human-readable representation. However, the `__code__` object (a `CodeType` object, in actuality) is immutable, and you can't assign to `co_code`. But as you already know, this isn't going to stop us at all.

All we need to do is change the contents of `__code__.co_code`'s bytes, and Python will magically run that when calling the function. For this, let's use a new example function, `add()`:

```py
def add(a: int, b: int) -> int:
    return a + b
```

Disassembling it yields:

```dis
          RESUME                   0
          LOAD_FAST_BORROW_LOAD_FAST_BORROW 1 (, )
          BINARY_OP                0 (+)
          RETURN_VALUE
```

Let's also look at a similar function, `subtract`:

```py
def subtract(a: int, b: int) -> int:
    return a - b
```

```dis
          RESUME                   0
          LOAD_FAST_BORROW_LOAD_FAST_BORROW 1 (, )
          BINARY_OP               10 (-)
          RETURN_VALUE
```

Notice that both are identical except for the parameter to `BINARY_OP`. We can also check the byte that was changed in `co_code`'s bytes directly:

```py
>>> add.__code__.co_code.hex()
'800057012c00000000000000000000002300'
>>> subtract.__code__.co_code.hex()
'800057012c0a000000000000000000002300'
```

The change is the 6th byte, from `00` (dec 0) to `0a` (dec 10). Let's test this by making `add` subtract numbers:

```py
>>> code = bytearray(add.__code__.co_code)
>>> code[5] = 0x0a
>>> add.__code__ = add.__code__.replace(co_code=bytes(code))
```

This only works because a `CodeType` object gives us the ability to create a new instance of it from the Python side - with `replace()`! This keeps everything else in the object intact while just replacing `co_code`. Then, Python just straight up lets us assign to `__code__` in the `__dict__` of the `FunctionType` object, which lets us, in-place and updating all references to `add()`, make the function now subtract instead. Now, when you call `add()`...

```py
>>> add(1, 2)
-1
```

### Bonus: Gaslighting the Current Frame

Remember how I mentioned `inspect`? Let's use it to do some even more horrible things! Unfortunately, because of optimizations in newer Python versions, we can't directly modify `co_code` on the fly. What we *can* do, though, is change the values that are supposed to be constant in our function. Because `co_consts` is a tuple, which is supposed to be immutable, it actually stores the real values of the constants in the bytecode. So...

```py
import inspect
import ctypes

class PyTupleObject(ctypes.Structure):
    _fields_ = [
        ('ob_refcnt', ctypes.c_ssize_t),
        ('ob_type', ctypes.c_void_p),
        ('ob_size', ctypes.c_ssize_t),
        ('ob_item', ctypes.c_void_p * 1) # Array of pointers
    ]

def myfunc():
    print("Hello, world!") # this creates a constant!

    frame = inspect.currentframe()
    consts = frame.f_code.co_consts
    target_index = consts.index("Hello, world!") # we get a handle on the constant we just made
    
    # we get a pointer to the tuple and find where the value we want to poke is...
    tuple_ptr = ctypes.cast(id(consts), ctypes.POINTER(PyTupleObject))
    slot_addr = ctypes.addressof(tuple_ptr.contents.ob_item) + (target_index * ctypes.sizeof(ctypes.c_void_p))

    slot = ctypes.cast(slot_addr, ctypes.POINTER(ctypes.c_void_p))
    new_const = "Goodbye, world!"
    slot.contents.value = id(new_const)

    print("Hello, world!") # this is the same constant as before, but we overwrote it!
```

Then, if `myfunc()` is called...

```py
>>> myfunc()
Hello, world!
Goodbye, world!
```

This doesn't corrupt the global state, either, like how changing the value of a `PyASCIIObject` that's been cached would - ouside of `myfunc()`, `"Hello, world!"` is still entirely normal and unchanged.

## 4. Making Something out of `None`thing

As many of you will expect by this point, `None` is also an object! In fact, it's another immutable one stuck at a constant location in memory for each runtime of CPython. I think you get the pattern by this point, so let's just figure out how to fuck with it! First, let's see where None is:

```py
>>> id(None)
140395397424176
```

At this point, you get how it'll be cast to a ctypes `POINTER` and all that jazz, but interestingly, all that is present in this object is that `PyObject_HEAD`.

```py
import ctypes

class PyNoneObject(ctypes.Structure):
    _fields_ = [
        ('ob_refcnt', ctypes.c_ssize_t),
        ('ob_type', ctypes.c_void_p),
    ]
```

If we cast the `id` of None to it, we can then see there are two fields we can modify. Messing with the `ob_refcnt` isn't that much fun, since it's an immortal object anyway (which means the ref count is largely ignored by the GC),so we're left with the `ob_type`.

Well, what happens if we set `None` to equal `0`? We can get the address of the `int` type with `id(int)`, but in order to make `None` hold a value, we need to awkwardly cast it to a new type:

```py
class PyVarObject(ctypes.Structure):
    _fields_ = [
        ('ob_refcnt', ctypes.c_ssize_t),
        ('ob_type', ctypes.c_void_p),
        ('ob_size', ctypes.c_ssize_t),  # <--- none doesn't actually have this!
        ('ob_digit', ctypes.c_uint * 1) # <--- or this!
    ]
```

But with this, we can do some fun stuff!

```py
>>> ptr = ctypes.cast(id(None), ctypes.POINTER(PyVarObject))
>>> from types import NoneType
>>> isinstance(None, NoneType)
True
>>> ptr.contents.ob_size = 12         # correct size for PyLong int with one digit
>>> ptr.contents.ob_digit[0] = 0      # like how we overwrote constant ints
>>> ptr.contents.ob_type = id(int)    # but now, we also overwrite the type!
```

And then...

```py
>>> None
0
>>> int(None)
0
>>> isinstance(None, NoneType)
False
>>> isinstance(None, int)
True
>>> None + 1
1
```

You might run into a segfault or two when exiting or trying to do... literally anything, but in the end it's okay since you made `None` an int!

```py
>>> exit()
fish: Job 1, 'python' terminated by signal SIGSEGV (Address boundary error)
```

## 5. The Call is Coming From Outside the House

Let's say I have this entirely normal code that calls a function and prints a variable:

```py
def innocent_func():
    x = 10
    myfunc()
    print(f"By the way, the value of x is {x}, in case you were wondering")
```

You would think, of course, that the value of `x` could in no way be influenced by the call to `myfunc` - but of course, you're wrong. Like with the previous `inspect` shenanigans, this relies on getting a frame from somewhere in the current runtime - this time, though, we use `sys`. We can get the frame of the caller by simply doing:

```py
>>> import sys
>>> sys._getframe(1)
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    sys._getframe(1)
    ~~~~~~~~~~~~~^^^
ValueError: call stack is not deep enough
```

Of course, this fails in the REPL because nothing is calling it - but it doesn't fail in IPython!

```py
In [1]: import sys

In [2]: sys._getframe(1)
Out[2]: <frame at 0x7f056a17b220, file '/home/nerd/.cache/uv/archive-v0/qL_s7bGL-JItrU1jpLiKf/lib/python3.14/site-packages/IPython/core/interactiveshell.py', line 3701, code run_code>
```

Since this is a `frame` object, it has the `f_locals` attribute, which allows *some* manipulation of the locals in the frame's current state, and if you were to do:

```py
caller_frame = sys._getframe(1)
caller_frame.f_locals['x'] = 1337
```

`x` would then equal 1337! To see it in action, all you have to do is:

```py
import sys
import inspect

def innocent_func():
    x = 10
    myfunc()
    print(f"By the way, the value of x is {x}, in case you were wondering")
    
def myfunc():
    caller_frame = sys._getframe(1)
    caller_frame.f_locals['x'] = 1337
    
innocent_func()
```

This is most useful primarily in the context of CTFs or other pyjails, and it's not as impressive as the other examples here, but it's still fun nonetheless.

## Conclusion

These are just a few ways you can break CPython - if you have learned anything from this post, it should be that Python's "safety" is a gentleman's agreement. The interpreter assumes you won't touch `ctypes` unless you're doing something reasonable. It assumes you won't use `id()` for pointer arithmetic. It assumes you are a rational programmer who wants their code to work.

But if you are willing to break those agreements, CPython is just a C program, and memory is just memory. Now, please, for the love of Guido, never put any of this in a pull request.
