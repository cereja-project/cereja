# Text and Data Utilities

The `mltools` module contains lightweight helpers for text preprocessing, tokenization, corpus splitting, and frequency
analysis.

## Frequency Counts

```python
import cereja as cj

freq = cj.Freq([1, 2, 3, 3, 10, 10, 4, 4, 4, 4])

print(freq.most_common(2))
print(freq.least_freq(2))
print(freq.probability)
```

## Text Preprocessing

```python
import cereja as cj

text = "Oi tudo bem?? meu nome e Joab!"

text = cj.preprocess.remove_extra_chars(text)
text = cj.preprocess.separate(text, sep=["?", "!"])
text = cj.preprocess.accent_remove(text)
```

For repeated preprocessing, configure a `Preprocessor`:

```python
import cereja as cj

preprocessor = cj.Preprocessor(
    stop_words=(),
    punctuation="!?,.",
    to_lower=True,
    is_remove_punctuation=False,
    is_remove_stop_words=False,
    is_remove_accent=True,
)

print(preprocessor.preprocess("Oi tudo bem?"))
```

## Tokenizer

```python
import cereja as cj

tokenizer = cj.Tokenizer(["my name is joab"], use_unk=True)
token_sequence, hash_ = tokenizer.encode("my name is someone else")
decoded = tokenizer.decode(token_sequence, hash_=hash_)
```

## Corpus

```python
import cereja as cj

source = ["how are you?", "my name is Joab", "I like coffee"]
target = ["como voce esta?", "meu nome e Joab", "Eu gosto de cafe"]

corpus = cj.Corpus(source_data=source, target_data=target, source_name="en", target_name="pt")
train, test = corpus.split_data()
```

`Corpus.split_data()` keeps test examples compatible with the vocabulary available in the training data.
