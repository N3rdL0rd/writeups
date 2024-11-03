rule CyberPanel_Babuk_Variant {
    meta:
        description = "A strain of ransomware based on the leaked Babuk source, with a hard-coded symmetric encryption key making it easy to decrypt."
        author = "N3rdL0rd"
        date = "2024-11-03"
        severity = "MODERATE"
		malware_family = "Babuk"
		hash = "53bf41beef030d39bf962e0a267544cc6fc7f67954e14d6bdf3de7738f3e6e9f"
        
    strings:
        $ext1 = ".woff2" ascii
        $ext2 = ".xlsx" ascii
        $ext3 = ".xlsm" ascii
        $ext4 = ".xltx" ascii
        $ext5 = ".xltm" ascii
        $ext6 = ".mhtml" ascii
        
        $op1 = "Encrypting: %s" ascii
        $op2 = "Crypted: %s" ascii
        $op3 = "Doesn't encrypted files: %d" ascii
        $op4 = "Encrypted files: %d" ascii
        $op5 = "Skipped files: %d" ascii
        $op6 = "Whole files count: %d" ascii
        
        $thread1 = "thread-pool-%d" ascii
        $thread2 = "thpool_init(): Could not allocate memory for thread pool" ascii
        $thread3 = "thpool_add_work(): Could not allocate memory for new job" ascii

    condition:
        uint32(0) == 0x464c457f and // ELF
        (
            // Must have either:
            (5 of ($ext*) and 3 of ($op*)) or
            (2 of ($thread*) and 2 of ($op*) and 3 of ($ext*)) or
            (4 of ($op*))
        )
}