

                        Problem E – Expanding STACKS!
                              Author : Giovanna Kobus Conrado, Brasil


Two customers a and b (where a enters the restaurant first) can have been in the same line if
and only if their relative order in the input is:
                                           +a -a +b -b
or:
                                           +a +b -b -a
as opposed to:
                                           +a +b -a -b
A set of customers can have been in the same line if pairwise they could have been in the same
line.
It is sufficient to view the customers as vertices, quadratically iterate through the pairs of
customers, and add an edge between them if they cannot be in the same line.
Now an assignment of customers to lines is a coloring of such a graph, thus the problem
boils down to determining whether the graph is bipartite and assigning the customers to lines
according to their color.
The complexity is O(N 2 ), as that will be the maximum number of edges in the generated
graph.

A faster approach
The problem can also be solved in O(N ).
An item is a chronologically ordered list of integers xi , indicating a sequence of “push xi ” events
that go all into the same stack in that order. Assume that two items can be concatenated in
O(1) and accessed like a stack (such as using a linked list).
A Node is a pair of items, such that both items must go into different stacks. Items in a Node
might be empty. A Node with one empty item is a Simple Node, representing a sequence of
pushes that must all be together on the same stack, but it can be any of the two stacks. A
Node with two empty items is itself empty and irrelevant, and can be deleted at any time.

The 2024 ICPC Latin America Championship
A NodeStack is a stack of Nodes. A NodeStack represents a set of many possible specific states
of a two-stack system: a consistent two-stack system is obtained by choosing for each Node,
precisely to which stack goes each of its items, then once that is chosen each stack contains all
the corresponding items concatenated in the NodeStack order.
We can actually keep the NodeStack dynamically when adding push / pop events: a push
event is easy, we can simply push a ([], [push x]) Node into the NodeStack. When a pop x
event appears, the corresponding push x event must be the top element (next to be popped)
in one item of the NodeStack. Additionally, all Nodes from the top of the NodeStack up to the
Node containing the push x event must be Simple Nodes (otherwise, no consistent two-stack
configuration has the push x event on the top of a stack, so it cannot be popped). Then we
pop the old push x event from its item, and concatenate all the Simple Nodes that were on the
stack on top of the push x Node, into the other item of that Node. That means: all of those
push events that occurred after push x must have occurred in “the other” stack, otherwise
push x cannot be on top and pop x would be impossible.