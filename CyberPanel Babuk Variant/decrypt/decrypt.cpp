#include <iostream>
#include <fstream>
#include <vector>
#include <cstdint>
#include <memory>
#include "sosemanuk.h"

constexpr size_t CHUNK_SIZE = 10 * 1024 * 1024; // 10MB
constexpr size_t KEY_SIZE = 32;

void decrypt_file(const std::string& input_file, const std::string& output_file, const std::string& key_file) {
    std::ifstream fin(input_file, std::ios::binary);
    std::ofstream fout(output_file, std::ios::binary);
    std::ifstream fkey(key_file, std::ios::binary);

    if (!fin || !fout || !fkey) {
        std::cerr << "Error opening files\n";
        return;
    }

    fin.seekg(0, std::ios::end);
    std::streamsize file_size = fin.tellg();
    if (file_size <= 32) {
        std::cerr << "File too small to decrypt.\n";
        return;
    }
    file_size -= 32; // ignore last 32 bytes
    fin.seekg(0, std::ios::beg);

    std::vector<unsigned char> key(KEY_SIZE);
    if (!fkey.read(reinterpret_cast<char*>(key.data()), KEY_SIZE)) {
        std::cerr << "Error reading key.\n";
        return;
    }

    sosemanuk_key_context key_ctx;
    sosemanuk_schedule(&key_ctx, key.data(), KEY_SIZE);

    sosemanuk_run_context run_ctx;
    sosemanuk_init(&run_ctx, &key_ctx, nullptr, 0);

    std::vector<unsigned char> buffer(CHUNK_SIZE);

    std::streamsize remaining = file_size;
    while (remaining > 0) {
        std::streamsize to_read = std::min(static_cast<std::streamsize>(CHUNK_SIZE), remaining);
        
        if (!fin.read(reinterpret_cast<char*>(buffer.data()), to_read)) {
            std::cerr << "Error reading input.\n";
            return;
        }

        sosemanuk_encrypt(&run_ctx, buffer.data(), buffer.data(), to_read);

        if (!fout.write(reinterpret_cast<char*>(buffer.data()), to_read)) {
            std::cerr << "Error writing to output.\n";
            return;
        }

        remaining -= to_read;
    }

    std::cout << "Decryption complete.\n";
}

int main(int argc, char *argv[]) {
    if (argc != 4) {
        std::cerr << "Usage: " << argv[0] << " <encrypted_file> <output_file> <key_file>\n";
        return EXIT_FAILURE;
    }
    
    decrypt_file(argv[1], argv[2], argv[3]);
    return EXIT_SUCCESS;
}