def pack_by_token_budget(tokenizer, tokens, max_length):
    """
    Packs tokens and labels into chunks that fit within the token budget of max_length after tokenization.

    :param tokenizer: The tokenizer
    :param tokens: Tokens
    :param max_length: Maximum token length
    :return: (tok_chunks, lab_chunks) after packing
    """
    chunks_t = []
    i = 0
    while i < len(tokens):
        j = i + 1
        while j <= len(tokens):
            enc = tokenizer([tokens[i:j]], is_split_into_words=True, add_special_tokens=True, truncation=False, padding=False)
            if len(enc["input_ids"][0]) <= max_length:
                j += 1
            else:
                break

        if j > len(tokens):
            j = len(tokens)

        if j == i:
            j = i + 1

        chunks_t.append(tokens[i:j])
        i = j

    return chunks_t
