

                                 Problem K – KMOP
                         Author : Alejandro Strejilevich de Loma, Argentina



BFS/DP solution
The problem can be modeled as a shortest path problem in a graph. Each node/state is defined
by three parameters w, ` and c, indicating that there is an acronym for the first w words that
ends in the `-th letter of the w-th word, terminating with c contiguous consonants. Parameter
w ranges from 0 to N , ` ranges from 1 to 3, and c ranges from 0 to 2. Each node (w, `, c) has
at most two direct successors: (w, ` + 1, c1 ) (include the next letter of the current word), and
(w + 1, 1, c2 ) (move to the next word, skipping the rest of the current word). Value ci is either
c + 1 or 0, depending on whether the target letter is a consonant or a vowel, respectively. The
solution is the length of a shortest path from node (0, 1, 0) to node (N, 1, c) (taking minimum
over c). Since the graph is an unweighted DAG, the shortest paths can be computed using
BFS. There are O(N ) nodes and each node has outdegree at most two, so there are O(N )
edges; thus the time complexity of the algorithm is O(N ). There is no need to explicitly build
the graph.
An equivalent solution using dynamic programming defines the function f (w, `, c) as the min-
imum length an acronym described by the state (w, `, c) can have. The required answer is
minc f (N, 1, c). Each value of the function can be computed in O(1), and then the time com-
plexity is O(N ).

Greedy solution
The idea of the greedy algorithm is starting with the shortest possible acronym and then adding
letters to make it pronounceable. Let `i,j be the j-th letter of the i-th word. Start with the
acronym A = `1,1 , `2,1 , . . . , `N,1 . While A is not pronounceable do the following.

  1. Locate in A the first three contiguous consonants T = `k,1 `k+1,1 `k+2,1 (as we will see,
     these letters are always the first letters of three contiguous words).

  2. If `k+1,2 is a vowel, insert it in A (`k,1 `k+1,1 `k+2,1 → `k,1 `k+1,1 `k+1,2 `k+2,1 ). Notice that
     this is the best option since it breaks the triplet T and possibly another triplet starting
     at `k+1,1 . Thus, if A is still not pronounceable, the first problematic triplet must start at
     `k+2,1 or later.

  3. If `k+1,2 is a not a vowel (it is a consonant or does not exist), T should not be broken by
     inserting letters between `k+1,1 and `k+2,1 : if `k+1,2 does not exist it cannot be inserted,
     while if it is actually a consonant there is no gain in inserting it. This is because inserting
     `k+1,2 would generate another problematic triplet starting where T starts. This new
     problematic triplet should be broken by inserting additional letters between `k,1 and
     `k+1,1 , but this additional letters would also break T .


The 2024 ICPC Latin America Championship
           (a) If `k,2 is a vowel, insert it in A (`k,1 `k+1,1 `k+2,1 → `k,1 `k,2 `k+1,1 `k+2,1 ). If A is still
               not pronounceable, the first problematic triplet must start at `k+1,1 or later.
           (b) If `k,2 is a consonant and `k,3 is a vowel, insert them in A (`k,1 `k+1,1 `k+2,1 → `k,1
               `k,2 `k,3 `k+1,1 `k+2,1 ). Again, if A is still not pronounceable, the first problematic
               triplet must start at `k+1,1 or later.
           (c) If `k,2 is a consonant and `k,3 is not a vowel (it is a consonant or does not exist), the
               triplet T cannot be broken (without generating another problematic triplet which
               would be unbreakable). The same situation occurs if `k,2 does not exist. In this
               cases there is no pronounceable acronym, and we are done.

     There is no need to explicitly initialize and update A; it is enough to maintain its length.
     Locating all the problematic triplets can be done in O(N ) since they start at increasing values
     of k. Each time a problematic triplet is found, updating the length of A can be done in constant
     time. Thus, the time complexity of the algorithm is O(N ). The python code below implements
     this approach.


 1   #!/usr/bin/env python3
 2
 3   import sys
 4
 5   def IsVowel(c):
 6       return c in 'AEIOUY'
 7
 8   L=N=int(sys.stdin.readline())
 9
10   Consonants=qTail=0
11   qWords=[None]*3
12
13   while True:
14       while Consonants<3:
15           if N:
16                N-=1
17                qTail=(qTail+1)%3
18                LastWord=sys.stdin.readline()[:3]
19                qWords[qTail]=LastWord+'X' # length is at least 3 because of EOL
20                Consonants= 0 if IsVowel(LastWord[0]) else Consonants+1
21           else:
22                print(L)
23                sys.exit(0)
24       MiddleWord=qWords[(qTail+2)%3]
25       if IsVowel(MiddleWord[1]):
26           L+=1
27           Consonants=1
28       else:
29           FirstWord=qWords[(qTail+1)%3]
30           if IsVowel(FirstWord[1]):
31                L+=1
32           elif IsVowel(FirstWord[2]):
33                L+=2
34           else:
35                print('*')
36                sys.exit(0)
37           Consonants=2




     The 2024 ICPC Latin America Championship