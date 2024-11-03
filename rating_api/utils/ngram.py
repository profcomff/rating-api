def generate_ngrams(text: str, n: int) -> set:
    "Создаёт сет `n`-грамм из переданного `text`"

    word_list = [f"  {word.strip(' .,/')} " for word in text.lower().split()]
    return {word[i : i + n] for word in word_list for i in range(len(word) - n + 1)}


def similarity(text1: str, text2: str, n: int = 3) -> float:
    """
    Определяет совпадение строк `text1` и `text2` по их `n`-граммам
    Возвращает значени float 0 - 1, где 1 - идентичные строки
    """

    if not text1 or not text2 or text1 == "" and text2 == "":
        return 0

    ngrams1 = generate_ngrams(text1, n)
    ngrams2 = generate_ngrams(text2, n)

    return float(len(ngrams1 & ngrams2)) / float(len(ngrams1 | ngrams2)) if text1 != "" or text2 != "" else 0.0
