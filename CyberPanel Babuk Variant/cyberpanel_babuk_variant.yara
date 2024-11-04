rule CyberPanel_Babuk_Variant {
    meta:
        description = "A strain of ransomware based on the leaked Babuk source, with a hard-coded symmetric encryption key making it easy to decrypt."
        author = "N3rdL0rd"
        date = "2024-11-03"
        severity = "MODERATE"
        malware_family = "Babuk"
        hash = "53bf41beef030d39bf962e0a267544cc6fc7f67954e14d6bdf3de7738f3e6e9f"
        
    strings:
        $ext1 = ".log" ascii
        $ext2 = ".vmx" ascii
        $ext3 = ".ovf" ascii
        $ext4 = ".vmdk" ascii
        $ext5 = ".vmxf" ascii
        $ext6 = ".vmsd" ascii
        $ext7 = ".vmsn" ascii
        $ext8 = ".vswp" ascii
        $ext9 = ".vmss" ascii
        $ext10 = ".vmem" ascii
        $ext11 = ".nvram" ascii
        $ext12 = ".ova" ascii
        $ext13 = ".frm" ascii
        $ext14 = ".idb" ascii
        $ext15 = ".php" ascii
        $ext16 = ".bak" ascii
        $ext17 = ".sql" ascii
        $ext18 = ".MYD" ascii
        $ext19 = ".MYI" ascii
        $ext20 = ".opt" ascii
        $ext21 = ".js" ascii
        $ext22 = ".css" ascii
        $ext23 = ".html" ascii
        $ext24 = ".svg" ascii
        $ext25 = ".woff" ascii
        $ext26 = ".woff2" ascii
        $ext27 = ".eot" ascii
        $ext28 = ".ico" ascii
        $ext29 = ".png" ascii
        $ext30 = ".jpg" ascii
        $ext31 = ".jpeg" ascii
        $ext32 = ".gif" ascii
        $ext33 = ".mp4" ascii
        $ext34 = ".asp" ascii
        $ext35 = ".jsp" ascii
        $ext36 = ".mp3" ascii
        $ext37 = ".zip" ascii
        $ext38 = ".gz" ascii
        $ext39 = ".tar" ascii
        $ext40 = ".bz2" ascii
        $ext41 = ".json" ascii
        $ext42 = ".bk" ascii
        $ext43 = ".doc" ascii
        $ext44 = ".pdf" ascii
        $ext45 = ".xlsx" ascii
        $ext46 = ".xls" ascii
        $ext47 = ".xlt" ascii
        $ext48 = ".et" ascii
        $ext49 = ".xlsm" ascii
        $ext50 = ".db" ascii
        $ext51 = ".csv" ascii
        $ext52 = ".xltx" ascii
        $ext53 = ".xltm" ascii
        $ext54 = ".mht" ascii
        $ext55 = ".mhtml" ascii
        $ext56 = ".dbf" ascii
        $ext57 = ".mdb" ascii
        $ext58 = ".vue" ascii
        
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
