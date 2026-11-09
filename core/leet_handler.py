"""Leet Speak替换模块 - a→@, e→3, i→1, o→0, s→$, t→7"""


def leet_speak(word):
    """Leet Speak变体：对每个可替换字符，生成替换和不替换两种情况"""
    if not word:
        return [word] if word is not None else []

    leet_map = {'a': '@', 'e': '3', 'i': '1', 'o': '0', 's': '$', 't': '7'}
    variants = [word]

    word_lower = word.lower()
    for i, char in enumerate(word_lower):
        if char in leet_map:
            new_variants = []
            for v in variants:
                new_variants.append(v)
                new_variants.append(v[:i] + leet_map[char] + v[i+1:])
            variants = new_variants

    return list(set(variants))


def leet_speak_simple(word):
    """简单Leet Speak：一次性替换所有可替换字符"""
    if not word:
        return [word] if word is not None else []

    leet_map = {'a': '@', 'e': '3', 'i': '1', 'o': '0', 's': '$', 't': '7'}
    result = []
    for ch in word:
        lower_ch = ch.lower()
        if lower_ch in leet_map:
            result.append(leet_map[lower_ch])
        else:
            result.append(ch)
    return [word, ''.join(result)]
