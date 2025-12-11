---
title: "Patching QLab (is simpler than you would think)"
date: "2024-10-27"
excerpt: "It's pretty easy to remove the license check from QLab, actually."
tags: ["rev", "cracking"]
---

Let me prefix this post by saying: QLab is an amazing piece of software. If you have the budget, please support the developers. This post purposefully doesn't provide pre-patched files, just observations from reverse-engineering QLab.

## Introduction

QLab is a theatre cueing system that allows you to control audio, video, lighting, and more from a centralized list of cues. It has a generous free tier and a lot of capabilities... until you want to add an audio filter or seriously use lighting. After discovering these issues, I ran to my director and begged her to buy tech a QLab license, but to no avail, since we were truly running on a shoestring in my community theater. So, I set out on my own quest...

## Recon and Initial Analysis

To start, I opened the Mach-O binary in aarch64 mode in Binary Ninja. I'm running this on a real physical Mac, which means that I'm stuck with Apple silicon and therefore, ARM. This doesn't prove to be too much of an issue, really, but analysis took exponentially longer as compared to x64 for some obscene reason. After about an hour of Binja chugging away at the binary, it finally loads fully. But once it does...

![symbols!](/static/posts/QLab/image.png)

Oh yes. Oh yes! Symbols! So many symbols! You really love to see it. Tracing everything back, most (if not all) of the licensing checks in the entire app trace back to `-[QLab licensedFor:]`. A simple patch of the last opcode gets us a function that always returns `0x1` (`true`):

```asm
; bool -[QLab licensedFor:](struct QLab* self, SEL sel, id licensedFor)
stp     x22, x21, [sp, #-0x30]! {__saved_x22} {__saved_x21}
stp     x20, x19, [sp, #0x10] {__saved_x20} {__saved_x19}
stp     x29, x30, [sp, #0x20] {__saved_x29} {__saved_x30}
add     x29, sp, #0x20 {__saved_x29}
mov     x19, x0
mov     x0, x2
bl      _objc_retain
mov     x20, x0
mov     x0, x19
bl      0x1005f6ff0  {data_100050424}
mov     x29, x29 {__saved_x29}
bl      _objc_retainAutoreleasedReturnValue
mov     x19, x0
mov     x2, x20
bl      0x1005f3d90  {data_100050438}
mov     x21, x0
mov     x0, x20
bl      _objc_release
mov     x0, x19
bl      _objc_release
mov     x0, #0x                                           ; <- Patched line
ldp     x29, x30, [sp, #0x20] {__saved_x29} {__saved_x30}
ldp     x20, x19, [sp, #0x10] {__saved_x20} {__saved_x19}
ldp     x22, x21, [sp], #0x30 {__saved_x22} {__saved_x21}
ret
```

And, of course, all the other checks for licensing just go to this one function:

```c
bool -[QLab licensedForAudio](struct QLab* self, SEL sel)
{
    /* tailcall */
    return _objc_msgSend(self, "licensedFor:");
}


bool -[QLab licensedForVideo](struct QLab* self, SEL sel)
{
    /* tailcall */
    return _objc_msgSend(self, "licensedFor:");
}


bool -[QLab licensedForLighting](struct QLab* self, SEL sel)
{
    /* tailcall */
    return _objc_msgSend(self, "licensedFor:");
}


bool -[QLab licensedForAnyType](struct QLab* self, SEL sel)
{
    if (!(-[QLab licensedForAudio](self, "licensedForAudio") & 1) && !(-[QLab licensedForVideo](self, "licensedForVideo") & 1))
        /* tailcall */
        return _objc_msgSend(self, "licensedForLighting");
    return 1;
}
```

In order to use this patch on a Mac, you'll have to resign the `.app` bundle with an ad-hoc key:

```zsh
codesign --force --deep --sign - /path/to/QLab-Patched.app
chmod -R +x /path/to/QLab-Patched.app
xattr -r /path/to/QLab-Patched.app
```

To verify that everything is signed correctly:

```zsh
codesign -vvv --deep --strict /path/to/QLab-Patched.app
```

## That's all, folks

This was much shorter of a post that I anticipated, frankly. I was expecting to have to patch a lot more than a single opcode, but here we are, with a patch that works for every single licensed feature with no hassle whatsoever. This feels a bit immoral to publish, so I might end up keeping this post private out of principle. But, if you are in the future reading this, clearly I published *something*.

As always, written with ❤️ by N3rdL0rd.
