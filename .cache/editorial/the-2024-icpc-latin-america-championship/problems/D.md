

                              Problem D – DiviDuelo
                                 Author : Pablo Blanc, Argentina


The answer depends on the factorization of N . We consider different cases:

   • If N = pα : All the divisors are multiples of p except for 1. Then the starting player wins
     except if he is forced to pick 1 as his last pick. This will happen only if the number of
     divisors is odd (α even).
   • If N = pα q β : We distinguish between the cases N = pq (with α = β = 1) and the
     remaining situations.
        – If N = pq: The starting player selects pq in the first turn. Then in his second (and
          last) turn picks p or q, he has secured that the GCD is not 1.
        – Otherwise: If N = pα q β and N 6= pq, we assume α ≥ 2. The second player has a
          winning strategy.
             ∗ If the total number of divisor is odd the second player can force the starting
               player to pick 1.

The 2024 ICPC Latin America Championship
               ∗ Otherwise, observe that the list of divisors contains the numbers 1, q, p, and p2 .
                 The second player can force the starting player to pick one number from the set
                 {1, q} and another from the set {p, p2 }, and therefore the GCD of the numbers
                 of the starting player will be 1.
                 To force the starting player, the second player will not pick a number from those
                 sets until the starting player picks one of the numbers, then the second player
                 picks the other. The starting player will be forced to pick one number in those
                 sets before the other player because the total number of divisors is even. This
                 way the starting player will end up picking one number from each set.
      • If N has at least 3 different prime divisors: The second player has a winning strategy.
        Let p, q, and r be distinct prime factors of N . Then, as in the previous case, the second
        player can force the starting player to pick one number from the set {1, p} and another
        from the set {q, r}, thereby securing a victory.

We conclude that the starting player has a winning strategy iff N = pα with α odd or N = pq.
                                                                  √
Finally, the problem can be solved by factoring the number in O( N ).