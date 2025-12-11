---
title: "Reversing and Decrypting a CyberPanel Babuk Variant"
date: "2024-11-03"
excerpt: "There have been a few reported cases of this particular strain of ransomware, and it has a unique security flaw that allows it to be universally decrypted."
tags: ["rev", "malware", "research"]
---

- Hash: `53bf41beef030d39bf962e0a267544cc6fc7f67954e14d6bdf3de7738f3e6e9f` (SHA256) from `./dont.run.me`
- Platform: x64 ELF
- Decompiled snippets are accessible in `./decompiled.c`.

## Writeup

***main()***

The entry for the application is simple:

```c
int __fastcall main(int argc, char **argv)
{
  int num_processors; // eax
  char *size_str; // rax

  if ( argc == 2 )                              // executable name, path
  {
    num_processors = sysconf(84);               // _SC_NPROCESSORS_ONLN
    thread_pool = create_threads(2 * num_processors);
    putchar(10);
    encrypt_dir(argv[1]);
    join_threads(thread_pool);
    destroy_threads(thread_pool);
    putchar(10);
    puts("Statistic:");
    puts("------------------");
    printf("Doesn't encrypted files: %d\n", total_file_count - total_encrypted_count - skipped_file_count);
    printf("Encrypted files: %d\n", total_encrypted_count);
    printf("Skipped files: %d\n", skipped_file_count);
    printf("Whole files count: %d\n", total_file_count);
    size_str = format_size(total_encrypted_size);
    printf("Crypted: %s\n", size_str);
    puts("------------------");
    putchar(10);
  }
  else
  {
    printf("Usage: %s /path\n", *argv);
  }
  return 0;
}
```

Interestingly, this sample seems to only encrypt the directory that it's passed, making it safe<sup>[1](#footnotes)</sup> to detonate on most systems. It uses a thread pool (see the C Thread Pool library<sup>[[3]](#references)</sup>) to encrypt files quickly and it prints a final count in the same format as Babuk.

***find_files_recursive()*** - *encrypt_dir()* in the attached decompilation

This is the actual meat and potatoes of this sample, and is one of the two major functions that was modified from the leaked Babuk source<sup>[[2]](#references)</sup>. Because this function is so long, it is not included here.

At it's core, this is nothing but a simple directory crawler. It goes through the directory it's given recursively and writes a ransom note to the root of it. Notably, the ransomware will **only** encrypt the files with following extensions:

`.frm, .idb, .php, .bak, .sql, .MYD, .MYI, .opt, .js, .css, .html, .svg, .woff, .woff2, .eot, .ico, .png, .jpg, .jpeg, .gif, .mp4, .asp, .jsp, .mp3, .zip, .gz, .tar, .bz2, .json, .bk, .doc, .pdf, .xlsx, .xls, .xlt, .et, .xlsm, .db, .csv, .xltx, .xltm, .mht, .mhtml, .dbf, .mdb, .vue`

!!! note
    Some sub-variants will check for other file extensions, specifically: `.log, .vmx, .ovf, .vmdk, .vmxf, .vmsd, .vmsn, .vswp, .vmss, .vmem, .nvram, .ova`

***encrypt_file()***

This is the other major modified function in the sample. In the original Babuk, ECC is used to generate an ephemeral encryption key for SOSEMANUK<sup>[[1]](#references)</sup> (a semi-obscure stream cipher), but in this sample, this functionality is removed and is instead replaced with a SHA256 hash of an uninitialized byte array with length `32` - which results in the following key:

```txt
          00 01 02 03 04 05 06 07  08 09 0A 0B 0C 0D 0E 0F
 
00000000  D7 F1 D7 DB 06 37 B3 71  F7 BC 73 92 16 5A 47 2D
00000010  A2 96 67 66 B8 A7 58 06  C7 73 2B 21 30 03 64 C6
```

This key is fed directly to SOSEMANUK to encrypt the file in 10MB chunks, with a trailing set of 32 bytes of zeros. If these zeros are included in normal decryption, they can cause invalid data to be returned - make sure to ignore them during decryption.

## Decryptor

A proof-of-concept decryptor for files encrypted by the sample is included in the `./decrypt` folder, and a sample of an encrypted file is located at `./test.json.encryp`.

Usage:

```txt
decrypt <encrypted_file> <output_file> <key_file>
```

## Indicators of Compromise

***Filename***

- `*.encryp`
- `help-readme.txt`

***Hashes***

- SHA256: `53bf41beef030d39bf962e0a267544cc6fc7f67954e14d6bdf3de7738f3e6e9f`
- SHA256: `113c3c3aeafbc59615cc23cd47b0cb1f22145ed6d7bfeca283c3fdf4d8076881`
- SHA256: `a1145bfafd1fe4ab5db7d03836af4289d0622bf596f30a50320accb02e337157`

***Other***

- TOX ID: `970F104D828F2696FF2508C0EFB3BEAB3220DFF8B7A45EBFBE86A1DBE2830B62CEBB32248B46`
- TOX ID: `A162BBD93F0E3454ED6F0B2BC39C645E9C4F88A80B271A93A4F55CF4B8310C2E27D1D0E0EE1B`

!!! note
    A YARA rule is available in `./cyberpanel_babuk_variant.yara`.

## Footnotes

1. Although running the sample on a folder is most likely safe, it is still advisable to run this in a VM due to potentially destructive actions being taken.

## References

1. The leaked [Babuk Ransomware Source](https://github.com/Hildaboo/BabukRansomwareSourceCode), from some random archive on GitHub
2. The eSTREAM Project's [documentation on SOSEMANUK](https://web.archive.org/web/20210507120806/https://www.ecrypt.eu.org/stream/sosemanukpf.html), and [Wikipedia too](https://en.wikipedia.org/wiki/SOSEMANUK)
3. The [C Thread Pool](https://github.com/Pithikos/C-Thread-Pool) library

And a profound thank you to you, dear reader, for suffering through this poorly written writeup, which was made with ❤️ by N3rdL0rd.
