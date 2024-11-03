# CyberPanel Babuk Variant decryptor

Not a patch, no undefined behaviour - 100% transparent.

## Building

`build.bat` or `build.sh`.

For MSVC (Windows) you'll need to run `vcvarsall.bat` in your shell session first.

## Usage

You'll need a key file extracted from the binary - one is provided in the `prebuilt` directory in this folder. Call it with:

```
decrypt <encrypted_file> <output_file> <key_file>
```

Look in `<output_file>` and you'll see the original contents of your file!

***Made with :heart: by N3rdL0rd***