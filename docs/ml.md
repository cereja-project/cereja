# 🧠 ML Package 

📊 **Freq**

```python
import cereja as cj

freq = cj.Freq([1, 2, 3, 3, 10, 10, 4, 4, 4, 4])
# Output -> Freq({1: 1, 2: 1, 3: 2, 10: 2, 4: 4})

freq.most_common(2)
# Output -> {4: 4, 3: 2}

freq.least_freq(2)
# Output -> {2: 1, 1: 1}

freq.probability
# Output -> OrderedDict([(4, 0.4), (3, 0.2), (10, 0.2), (1, 0.1), (2, 0.1)])

freq.sample(min_freq=1, max_freq=2)
# Output -> {3: 2, 10: 2, 1: 1, 2: 1}

# Save json file.
freq.to_json('./freq.json')
```

🧹 **Text Preprocess**
```python
import cereja as cj

text = "Oi tudo bem?? meu nome é joab!"

text = cj.preprocess.remove_extra_chars(text)
print(text)
# Output -> 'Oi tudo bem? meu nome é joab!'

text = cj.preprocess.separate(text, sep=['?', '!'])
# Output -> 'Oi tudo bem ? meu nome é joab !'

text = cj.preprocess.accent_remove(text)
# Output -> 'Oi tudo bem ? meu nome e joab !'

# and more ..

# You can use class Preprocessor ...
preprocessor = cj.Preprocessor(stop_words=(),
                               punctuation='!?,.', to_lower=True, is_remove_punctuation=False,
                               is_remove_stop_words=False,
                               is_remove_accent=True)

print(preprocessor.preprocess(text))
# Output -> 'oi tudo bem ? meu nome e joab !'

print(preprocessor.preprocess(text, is_destructive=True))
# Output -> 'oi tudo bem meu nome e joab'

```

🔣 **Tokenizer**
```python
import cereja as cj

text = ['oi tudo bem meu nome é joab']

tokenizer = cj.Tokenizer(text, use_unk=True)

# tokens 0 to 9 is UNK
# hash_ used to replace UNK
token_sequence, hash_ = tokenizer.encode('meu nome é Neymar Júnior')
# Output -> [([10, 12, 11, 0, 1], 'eeb755960ce70c')]

decoded_sequence = tokenizer.decode(token_sequence)
# Output -> ['meu', 'nome', 'é', '{0}', '{1}']

decoded_sequence = ' '.join(decoded_sequence)

tokenizer.replace_unks(decoded_sequence, hash_)
# Output -> 'meu nome é Neymar Júnior'

```

⏸ **Corpus**

Great training and test separator.

```python
import cereja as cj

X = ['how are you?', 'my name is Joab', 'I like coffee', 'how are you joab?', 'how', 'we are the world']
Y = ['como você está?', 'meu nome é Joab', 'Eu gosto de café', 'Como você está joab?', 'como', 'Nós somos o mundo']

corpus = cj.Corpus(source_data=X, target_data=Y, source_name='en', target_name='pt')
print(corpus)  # Corpus(examples: 6 - source_vocab_size: 13 - target_vocab_size:15)
print(corpus.source)  # LanguageData(examples: 6 - vocab_size: 13)
print(corpus.target)  # LanguageData(examples: 6 - vocab_size: 15)

corpus.source.phrases_freq
# Counter({'how are you': 1, 'my name is joab': 1, 'i like coffee': 1, 'how are you joab': 1, 'how': 1, 'we are the world': 1})

corpus.source.word_freq
# Counter({'how': 3, 'are': 3, 'you': 2, 'joab': 2, 'my': 1, 'name': 1, 'is': 1, 'i': 1, 'like': 1, 'coffee': 1, 'we': 1, 'the': 1, 'world': 1})

corpus.target.phrases_freq
# Counter({'como você está': 1, 'meu nome é joab': 1, 'eu gosto de café': 1, 'como você está joab': 1, 'como': 1, 'nós somos o mundo': 1})

corpus.target.words_freq
# Counter({'como': 3, 'você': 2, 'está': 2, 'joab': 2, 'meu': 1, 'nome': 1, 'é': 1, 'eu': 1, 'gosto': 1, 'de': 1, 'café': 1, 'nós': 1, 'somos': 1, 'o': 1, 'mundo': 1})

# split_data function guarantees test data without data identical to training
# and only with vocabulary that exists in training
train, test = corpus.split_data()  # default percent of training is 80%
```