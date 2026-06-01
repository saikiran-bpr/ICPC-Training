                             Problem L – LED Matrix
                        Author : Alejandro Strejilevich de Loma, Argentina


The solution is ad hoc. Let m be a row of the matrix and let p be the corresponding row of the
pattern. m properly displays p if and only if all the LEDs in m are good or all the LEDs in p are
off. This can be checked in O(C + K). The whole matrix properly displays the whole pattern
if and only if this happens for every row. The cost of the algorithm is O(R × (C + K)).




The 2024 ICPC Latin America Championship