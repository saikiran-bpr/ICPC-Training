                             Problem G – Greek Casino
                                     Author : Célio Passos, Brasil


The DP recurrence
We should first ensure that the expected value is indeed finite (this also implies that the
process ends in a finite number of steps with probability 1). Let X denote the random variable
indicating how many coins are   P awarded and let py denote the probability that number y is
sampled (that is, py = Wy / ( i Wi )). We can think of the process as a random walk over the
numbers 1, 2, . . . , N . A path ending on a can only include divisors of a itself. Thus:
                                           X
                                   E(X) =      P(X ≥ k)
                                             k≥1
                                              N
                                                                             !k
                                             XX              X
                                         ≤                              pb
                                             k≥1 a=1      b divides a
                                               X                       k
                                         ≤N            1 − min pa
                                                              a
                                               k≥1
                                         <∞
where we are summing over all possible last numbers a of a path length of k.
Now let’s define                                     X
                                             Ea =          P(P )
                                                      P
where the summation goes over all paths P ending on a. Note that Ea is exactly the expected
number of times the token will go to (or stay at) slot a, therefore
                                                     N
                                                     X
                                         E(X) =            Ea − 1.
                                                     a=1

We need to subtract 1 here because the contestant doesn’t get a coin in the beginning when
the token is at slot 1. Also,              X
                                 Ec =              pb Ea
                                              a,b:LCM(a,b)=c
for c > 1 and E1 = 1 + p1 E1 . We can rewrite this as E = p ∗ E + 1, where ∗ denotes the LCM
convolution, and rearrange it:
                                       (1 − p) ∗ E = 1
The number 1 here is actually the array (1, 0, 0, . . . , 0), which acts as the multiplicative identity.

LCM convolution technique
Let’s denote by T the transformation (on arrays) defined by
                                               X
                                   T (A)k =           Ad
                                                     d divides k

It is easy to compute its inverse (writing a formula may be complicated, but given T (A) we
can easily compute the original value A). Now, with the fact that a and b both divide c if and
only if LCM (a, b) divides c, we can write
                                     T (A)     T (B) = T (A ∗ B)
where    denotes pointwise multiplication. Thus, given T (A ∗ B) (non-zero in our case) and
T (A), we can easily compute T (B) and, inverting the transformation, also B itself.

The 2024 ICPC Latin America Championship
Final solution
Just let A = 1 − p and B = E and apply the previous facts. The complexity is O(N log N ).

Alternative approach
There’s also a more elementary approach. First, compute the sorted list of divisors of all
numbers up to N using a standard O(N log N ) sieve.
For each number x, 1 ≤ x ≤ N , we can compute the probability that the token reaches slot
number x and the expected amount of coins awarded until then (given that it reaches x).
For the transition from x to y (y is a multiple of x), look at the factorization of x and y. When
going from x to y, some exponents grow (possibly from 0 to a positive value for “new” primes),
while others remain the same. Those that grow must be present in z for LCM(x, z) = y. Those
that stay the same must be lower or equal in z than in x. So that means z = f · d, where f is
“a fixed integer composed of the power primes with larger exponent in y than in x”, and d is
any divisor of “the other primes” in x, which is itself a divisor of x and thus a number at most
x that has precomputed list of divisors by our N log N sieve.
The number of possible z are the number of divisors d such that f · d ≤ N , and the sum of
their weights defines the transition probability.
If we consider all the triples (x, y, d) that we iterate, all of them are different. This means that
the number of iterations is bound by the number of triples (d, x, y) such that d divides x and
x divides y (and all these numbers are ≤ N ). There are O(N log2 N ) triples in total and that
is the complexity of this approach.


                                                         N X
                            X     X        X             X   N
                                                 1≤
                                                                      ad
                            d=1 x=ad≤N y=bad≤N           d=1 ad≤N
                                                           N
                                                           X 1 X 1
                                                   =N
                                                                 d          a
                                                           d=1       a≤ N
                                                                        d
                                                           N
                                                           X 1               N
                                                   =N                O(log     )
                                                                 d           d
                                                           d=1
                                                   = O(N log2 N )