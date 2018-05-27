#!/usr/bin/env python
# -*- coding: utf-8 -*-

# -----------------
# Реализуйте функцию best_hand, которая принимает на вход
# покерную "руку" (hand) из 7ми карт и возвращает лучшую
# (относительно значения, возвращаемого hand_rank)
# "руку" из 5ти карт. У каждой карты есть масть(suit) и
# ранг(rank)
# Масти: трефы(clubs, C), пики(spades, S), червы(hearts, H), бубны(diamonds, D)
# Ранги: 2, 3, 4, 5, 6, 7, 8, 9, 10 (ten, T), валет (jack, J), дама (queen, Q), король (king, K), туз (ace, A)
# Например: AS - туз пик (ace of spades), TH - дестяка черв (ten of hearts), 3C - тройка треф (three of clubs)

# Задание со *
# Реализуйте функцию best_wild_hand, которая принимает на вход
# покерную "руку" (hand) из 7ми карт и возвращает лучшую
# (относительно значения, возвращаемого hand_rank)
# "руку" из 5ти карт. Кроме прочего в данном варианте "рука"
# может включать джокера. Джокеры могут заменить карту любой
# масти и ранга того же цвета, в колоде два джокерва.
# Черный джокер '?B' может быть использован в качестве треф
# или пик любого ранга, красный джокер '?R' - в качестве черв и бубен
# любого ранга.

# Одна функция уже реализована, сигнатуры и описания других даны.
# Вам наверняка пригодится itertoolsю
# Можно свободно определять свои функции и т.п.
# -----------------

import itertools

def hand_rank(hand):
    """Возвращает значение определяющее ранг 'руки'"""
    assert (len(hand) == 5)
    ranks = card_ranks(hand)
    if straight(ranks) and flush(hand):
        return (8, max(ranks))
    elif kind(4, ranks):
        return (7, kind(4, ranks), kind(1, ranks))
    elif kind(3, ranks) and kind(2, ranks):
        return (6, kind(3, ranks), kind(2, ranks))
    elif flush(hand):
        return (5, ranks)
    elif straight(ranks):
        return (4, max(ranks))
    elif kind(3, ranks):
        return (3, kind(3, ranks), ranks)
    elif two_pair(ranks):
        return (2, two_pair(ranks), ranks)
    elif kind(2, ranks):
        return (1, kind(2, ranks), ranks)
    else:
        return (0, ranks)


RANK_LIST = '2 3 4 5 6 7 8 9 T J Q K A'.split()
RANK_PRIORITIES = {RANK_LIST[n]: n for n in range(0, len(RANK_LIST))}

def card_ranks(hand):
    """Возвращает список рангов (его числовой эквивалент), отсортированный от большего к меньшему"""
    assert (len(hand) == 5)
    return sorted(map(lambda c: c[:1], hand), key=lambda x: RANK_PRIORITIES[x], reverse = True )


def flush(hand):
    """Возвращает True, если все карты одной масти"""
    assert (len(hand) == 5)
    s = None
    for c in hand:
        if s is None:
            s = c[1:2]
        elif s != c[1:2]:
            s = None
            break
    return s is not None


def straight(ranks):
    """Возвращает True, если отсортированные ранги формируют последовательность 5ти, где у 5ти карт ранги идут по порядку (стрит)"""
    assert (len(ranks) == 5)
    s = None
    for r in ranks:
        if s is None:
            s = RANK_PRIORITIES[r]
        elif s - 1 == RANK_PRIORITIES[r]:
            s = s - 1
        else:
            s = None
            break
    return s is not None


def kind(n, ranks):
    """Возвращает первый ранг, который n раз встречается в данной руке. Возвращает None, если ничего не найдено"""
    assert (len(ranks) == 5)
    kind = {}
    for r in ranks:
        if r not in kind:
            kind[r] = 1
        else:
            kind[r] = kind[r] + 1
    for r in kind:
        if kind[r] == n:
            return r
    return None


def two_pair(ranks):
    """Если есть две пары, то возврщает два соответствующих ранга, иначе возвращает None"""
    assert (len(ranks) == 5)
    kind = {}
    for r in ranks:
        if r not in kind:
            kind[r] = 1
        else:
            kind[r] = kind[r] + 1
    pairs = []
    for r in kind:
        if kind[r] >= 2:
            pairs.append(r)
    return pairs if len(pairs) == 2 else None


def best_hand(hand):
    """Из "руки" в 7 карт возвращает лучшую "руку" в 5 карт """
    rank = None
    best = None
    for h in itertools.combinations(hand, 5):
        r = hand_rank(h)
        if r is not None and (rank is None or rank < r[0]):
            rank = r[0]
            best = h
    return best


BLACK_JOKER = [ x[0]+x[1] for x in itertools.product(RANK_LIST, ['C', 'S']) ]
RED_JOKER = [ x[0]+x[1] for x in itertools.product(RANK_LIST, ['D', 'H']) ]

def best_wild_hand(hand):
    """best_hand но с джокерами"""
    rank = None
    best = None

    cards = []
    jokers = []

    for c in hand:
        if c == '?B':
            jokers.append(BLACK_JOKER)
        elif c == '?R':
            jokers.append(RED_JOKER)
        else:
            cards.append(c)
    set_cards = { x for x in cards }
    for joker_hand in itertools.product(*jokers):
        skip = False
        for j in joker_hand:
            if j in set_cards:
                skip = True
                break
        if skip:
            continue
        real_hand = itertools.chain(cards, joker_hand)
        for h in itertools.combinations(real_hand, 5):
            r = hand_rank(h)
            if r is not None and (rank is None or rank < r[0]):
                rank = r[0]
                best = h
    return best


def test_best_hand():
    print ("test_best_hand...")
    assert (sorted(best_hand("6C 7C 8C 9C TC 5C JS".split()))
            == ['6C', '7C', '8C', '9C', 'TC'])
    assert (sorted(best_hand("TD TC TH 7C 7D 8C 8S".split()))
            == ['7C', '7D', 'TC', 'TD', 'TH'])
    # другой вариант 3+2 встречается раньше
    # assert (sorted(best_hand("TD TC TH 7C 7D 8C 8S".split()))
    #         == ['8C', '8S', 'TC', 'TD', 'TH'])
    assert (sorted(best_hand("JD TC TH 7C 7D 7S 7H".split()))
            == ['7C', '7D', '7H', '7S', 'JD'])
    print ('OK')


def test_best_wild_hand():
    print ("test_best_wild_hand...")
    assert (sorted(best_wild_hand("6C 7C 8C 9C TC 5C ?B".split()))
            == ['6C', '7C', '8C', '9C', 'TC'])
    # другой вариант флеш-страйка встречается раньше
    # assert (sorted(best_wild_hand("6C 7C 8C 9C TC 5C ?B".split()))
    #         == ['7C', '8C', '9C', 'JC', 'TC'])
    assert (sorted(best_wild_hand("TD TC 5H 5C 7C ?R ?B".split()))
            == ['5C', '5D', '5H', '5S', 'TD'])
    # другой вариант 4+1 встречается раньше
    # assert (sorted(best_wild_hand("TD TC 5H 5C 7C ?R ?B".split()))
    #         == ['7C', 'TC', 'TD', 'TH', 'TS'])
    assert (sorted(best_wild_hand("JD TC TH 7C 7D 7S 7H".split()))
            == ['7C', '7D', '7H', '7S', 'JD'])
    print ('OK')


if __name__ == '__main__':
    test_best_hand()
    test_best_wild_hand()
