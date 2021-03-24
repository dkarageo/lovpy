import itertools
import copy

import networkx
from networkx.readwrite.graphml import write_graphml
from networkx.algorithms.simple_paths import all_simple_edge_paths
from networkx.drawing.nx_pylab import draw_networkx, draw_networkx_edge_labels, draw_networkx_edges
from matplotlib import pyplot as plt

from logipy.graphs.colorizable_digraph import ColorizableDiGraph
from logipy.logic.logical_operators import *
from logipy.logic.timestamps import *
from logipy.monitor.time_source import get_global_time_source


TIMESTAMP_PROPERTY_NAME = "timestamp"
IMPLICATION_PROPERTY_NAME = "implication"
TASK_PROPERTY_NAME = "task_property"
ASSUMPTION_GRAPH = "assumption"
CONCLUSION_GRAPH = "conclusion"


class TimedPropertyGraph:
    def __init__(self, time_source=get_global_time_source()):
        self.graph = ColorizableDiGraph()
        self.root_node = None
        self.time_source = time_source
        self.property_textual_representation = None

    def logical_and(self, property_graph, timestamp=None):
        if property_graph.graph.number_of_nodes() == 0:
            # Nothing to do if given graph is empty.
            return

        was_empty = self.graph.number_of_nodes() == 0

        timestamp1 = timestamp
        timestamp2 = timestamp

        if not timestamp:
            timestamp1 = self.get_most_recent_timestamp()
            timestamp2 = property_graph.get_most_recent_timestamp()
        if isinstance(timestamp1, RelativeTimestamp):
            timestamp1.set_time_source(self.time_source)
        if isinstance(timestamp2, RelativeTimestamp):
            timestamp2.set_time_source(self.time_source)

        self.graph.add_edges_from(property_graph.graph.edges(data=True))
        if not was_empty:
            # TODO: Implement recursive naming.
            and_node = AndOperator(self.get_root_node(), property_graph.get_root_node())
            self._add_edge(and_node, self.get_root_node(), {TIMESTAMP_PROPERTY_NAME: timestamp1})
            self._add_edge(and_node, property_graph.get_root_node(),
                           {TIMESTAMP_PROPERTY_NAME: timestamp2})
        else:
            self.root_node = property_graph.get_root_node()

    def logical_not(self, timestamp=None):
        if not timestamp:
            timestamp = self.get_most_recent_timestamp()
        if timestamp and isinstance(timestamp, RelativeTimestamp):
            timestamp.set_time_source(self.time_source)
        # TODO: Implement recursive naming.
        not_node = NotOperator(self.get_root_node())
        self._add_edge(not_node, self.get_root_node(), {TIMESTAMP_PROPERTY_NAME: timestamp})

    def logical_implication(self, property_graph, timestamp=None):
        if not self.get_root_node():
            raise Exception("Implication cannot be performed with an empty assumption.")
        if not property_graph.get_root_node():
            raise Exception("Implication cannot be performed with an empty conclusion.")

        # TODO: Implement recursive naming.
        impl_node = ImplicationOperator(self.get_root_node(), property_graph.get_root_node())

        if not timestamp:
            assumption_timestamp = self.get_most_recent_timestamp()
            conclusion_timestamp = property_graph.get_most_recent_timestamp()
        else:
            timestamp.set_time_source(self.time_source)
            assumption_timestamp = timestamp
            conclusion_timestamp = timestamp

        self.graph.add_edges_from(property_graph.graph.edges(data=True))
        self._add_edge(impl_node, self.get_root_node(),
                       {TIMESTAMP_PROPERTY_NAME: assumption_timestamp,
                       IMPLICATION_PROPERTY_NAME: ASSUMPTION_GRAPH})
        self._add_edge(impl_node, property_graph.get_root_node(),
                       {TIMESTAMP_PROPERTY_NAME: conclusion_timestamp,
                       IMPLICATION_PROPERTY_NAME: CONCLUSION_GRAPH})

    def set_timestamp(self, timestamp):
        """Sets given timestamp, as the timestamp of all edges of the graph.

        Set timestamp should not be used on a property graph after it has been used
        as an operand on a logical operation with another graph.
        """
        if not isinstance(timestamp, Timestamp):
            raise Exception("Only instances of Timestamp and its subclasses are allowed.")

        # Current implementation provides a single time source for all relative timestamps.
        if isinstance(timestamp, RelativeTimestamp):
            timestamp.set_time_source(self.time_source)

        for u, v in self.graph.edges():
            self.graph[u][v].update({TIMESTAMP_PROPERTY_NAME: timestamp})

    def is_uniform_timestamped(self, timestamp=None):
        edges = list(self.graph.edges(data=TIMESTAMP_PROPERTY_NAME))
        if not timestamp:
            timestamp = edges[0][2]
        for edge in edges:
            if timestamp.is_absolute() != edge[2].is_absolute():
                # All timestamps should either be absolute or relative.
                return False

            if timestamp.is_absolute() and (
                    timestamp.get_absolute_value() != edge[2].get_absolute_value()):
                # Absolute timestamps should have exact the same value.
                return False
            elif not timestamp.is_absolute() and not timestamp.matches(edge[2]):
                # Relative timestamps should have a common interval.
                return False
        return True

    def get_root_node(self):
        return self.root_node

    def set_time_source(self, time_source):
        self.time_source = time_source
        for edge in self.graph.edges(data=TIMESTAMP_PROPERTY_NAME):
            if isinstance(edge[2], RelativeTimestamp):
                edge[2].set_time_source(time_source)

    def get_most_recent_timestamp(self):
        timestamps = [e[2] for e in self.get_graph().edges(data=TIMESTAMP_PROPERTY_NAME)]
        return max(timestamps) if timestamps else None

    def get_top_level_implication_subgraphs(self):
        assumption = None
        conclusion = None

        if isinstance(self.root_node, ImplicationOperator):
            root_edges = list(self.graph.edges(self.root_node, data=IMPLICATION_PROPERTY_NAME))
            for edge in root_edges:
                if edge[2] == ASSUMPTION_GRAPH:
                    assumption = self.graph.subgraph(networkx.dfs_postorder_nodes(
                        self.graph, edge[1]))
                elif edge[2] == CONCLUSION_GRAPH:
                    conclusion = self.graph.subgraph(networkx.dfs_postorder_nodes(
                        self.graph, edge[1]))

        return self._inflate_property_graph_from_subgraph(assumption), \
            self._inflate_property_graph_from_subgraph(conclusion)

    def replace_subgraph(self, old_subgraph, new_subgraph):
        matching_cases, _, original_timestamps, cases_timestamps = \
            self.find_equivalent_subgraphs(old_subgraph)
        if not matching_cases:
            return False

        all_matching_paths = matching_cases[0]  # TODO: pass selection to prover
        matching_timestamps = cases_timestamps[0]

        # Find the upper node where all those paths connect.
        if len(all_matching_paths) > 1:
            for edge in all_matching_paths[0][::-1]:
                for path in all_matching_paths:
                    if not _edges_match(path[-1], edge):
                        break
                else:
                    for path in all_matching_paths:
                        path.remove(edge)
                        continue
                break

        # Add the new subgraph as an unconnected component.
        if new_subgraph:
            old_subgraph_timestamp = max(matching_timestamps)  # first moment the structure holds

            for edge in new_subgraph.get_graph().edges(data=TIMESTAMP_PROPERTY_NAME):
                # TODO: Consider if it is required to assign timestamps according to relative ones.
                # Replace relative timestamps with the absolute timestamp when old subgraph
                # firstly holds.
                timestamp = edge[2]
                if not timestamp.is_absolute():
                    timestamp = old_subgraph_timestamp
                self._add_edge(edge[0], edge[1], {TIMESTAMP_PROPERTY_NAME: timestamp})

            # Intervene an AND node between the upper non and node of matching subgraph
            # and its predecessors.
            upper_common_node = all_matching_paths[0][-1][0]
            and_node = AndOperator(upper_common_node, new_subgraph.get_root_node())
            and_timestamp = max(
                *(e[2] for e in self.graph.out_edges(upper_common_node, data=TIMESTAMP_PROPERTY_NAME)))
            predecessors = list(self.graph.predecessors(upper_common_node))
            for predecessor in predecessors:
                t = self.graph.edges[predecessor, upper_common_node][TIMESTAMP_PROPERTY_NAME]
                self.graph.remove_edge(predecessor, upper_common_node)
                self._add_edge(predecessor, and_node, {TIMESTAMP_PROPERTY_NAME: t})
            self._add_edge(and_node, upper_common_node, {TIMESTAMP_PROPERTY_NAME: and_timestamp})
            self._add_edge(and_node, new_subgraph.get_root_node(),
                           {TIMESTAMP_PROPERTY_NAME: and_timestamp})

        # Remove old edges and nodes that doesn't participate in any other path.
        #self._logically_remove_path_set(all_matching_paths)

        return True

    def remove_subgraph(self, subgraph):
        _, matching_groups, found = self._find_equivalent_path_structure(subgraph)
        self._logically_remove_path_set([g[0] for g in matching_groups])

    def contains_property_graph(self, property_graph):
        matching_cases, _, _, _ = self.find_equivalent_subgraphs(property_graph)
        return bool(matching_cases)

        # property_leaves = _get_leaf_nodes(property_graph)
        #
        # # Start from the leaves in property graph and make sure they exist in current graph.
        # for property_leaf in property_leaves:
        #     if not self.get_graph().has_node(property_leaf):
        #         return False
        #
        # # Make sure that for every path from a leaf node to the root node in property
        # # graph, there exists an equivalent and time-matching path from a leaf node
        # # to the root node in current graph. Equivalent means that between two
        # # connected nodes in property graph, whose depth differs by 1, only AND nodes
        # # can be inserted in current graph.
        # for property_leaf in property_leaves:
        #     _, _, matched = self.find_time_matching_paths_from_node_to_root(
        #         property_leaf, property_graph, property_leaf)
        #     if not matched:
        #         return False
        #
        # return True

    # def find_time_matching_paths_from_node_to_root(self, start_node, other_graph, other_start_node):
    #     matched_paths, matching_groups, found = self.find_equivalent_paths_from_node_to_root(
    #         start_node, other_graph, other_start_node)
    #
    #     # Check that for every matched path, there is at least one with matching timestamps.
    #     for i in range(len(matched_paths)):
    #         matched_path = matched_paths[i]
    #         matching_paths = matching_groups[i]
    #         matched_path_timestamp = _find_path_timestamp(matched_path)
    #
    #         # TODO: Implement time matching for timesources different than current one.
    #         # for matching_path in matching_paths:
    #         #     if not _find_path_timestamp(matching_path).matches(matched_path_timestamp):
    #         #         matching_paths.remove(matching_path)
    #
    #         if not matching_paths:
    #             matched_paths.remove(matched_path)
    #
    #     return matched_paths, matching_groups, bool(matched_paths)
    #
    # def find_equivalent_paths_from_node_to_root(self, start_node, other_graph, other_start_node):
    #     # TODO: Reimplement this method in a more elegant way.
    #     paths_to_upper_non_and_other_nodes = _find_path_to_upper_non_and_nodes(
    #         other_graph, other_start_node)
    #     paths_to_upper_non_and_current_nodes = _find_path_to_upper_non_and_nodes(self, start_node)
    #
    #     # If there are still nodes in other graph to be validated, while current graph has
    #     # reached to root, then no matching paths has been found.
    #     if paths_to_upper_non_and_other_nodes and not paths_to_upper_non_and_current_nodes:
    #         return [], [], False
    #     # Also, if other graph has reached to root, while current graph still contains non and
    #     # node to be validated, then no matching paths has been found.
    #     elif not paths_to_upper_non_and_other_nodes and paths_to_upper_non_and_current_nodes:
    #         matching_paths = _find_clean_paths_to_root(self, start_node)
    #         matched_paths = []
    #         if matching_paths:
    #             matched_paths = _find_clean_paths_to_root(other_graph, other_start_node)
    #         return matched_paths, [matching_paths for p in matched_paths], bool(matched_paths)
    #     # If non-and upper paths are empty in both other and current graphs, then the requested
    #     # one has been validated.
    #     elif not paths_to_upper_non_and_other_nodes and not paths_to_upper_non_and_current_nodes:
    #         matched_paths = _find_clean_paths_to_root(other_graph, other_start_node)
    #         matching_paths = _find_clean_paths_to_root(self, start_node)
    #         return matched_paths, [matching_paths for p in matched_paths], True
    #
    #     matched_other_paths = []
    #     matching_current_path_groups = []
    #
    #     for other_upper_path in paths_to_upper_non_and_other_nodes:  # paths to be validated
    #         other_upper_path_matched = False
    #
    #         for current_upper_path in paths_to_upper_non_and_current_nodes:
    #
    #             other_upper_path_non_and_node = other_upper_path[-1][0]
    #             current_upper_path_non_and_node = current_upper_path[-1][0]
    #
    #             if (isinstance(other_upper_path_non_and_node, LogicalOperator) and
    #                 isinstance(current_upper_path_non_and_node, LogicalOperator) and
    #                 current_upper_path_non_and_node.logically_matches(
    #                         other_upper_path_non_and_node)) or (
    #                     other_upper_path_non_and_node == current_upper_path_non_and_node):
    #
    #                 matched_paths, matching_groups, found = \
    #                     self.find_equivalent_paths_from_node_to_root(
    #                         current_upper_path_non_and_node,
    #                         other_graph,
    #                         other_upper_path_non_and_node
    #                     )
    #
    #                 # The matched and matching paths should be prepended with the subpaths up
    #                 # to the node where search started.
    #                 if found:
    #                     other_upper_path_matched = True
    #                     if not matched_paths:
    #                         # Path returned empty, because successfully terminated to root node.
    #                         matched_other_paths.append(other_upper_path)
    #                         matching_current_path_groups.append([current_upper_path])
    #                     else:
    #                         for p in matched_paths:
    #                             matched_other_paths.append([*other_upper_path, *p])
    #                         for matching_group in matching_groups:
    #                             matching_current_paths = []
    #                             for p in matching_group:
    #                                 matching_current_paths.append([*current_upper_path, *p])
    #                             matching_current_path_groups.append(matching_current_paths)
    #         if not other_upper_path_matched:  # Not matching a single path, is enough to fail.
    #             return [], [], False
    #
    #     return matched_other_paths, matching_current_path_groups, bool(matched_other_paths)

    def export_to_graphml_file(self, path):
        write_graphml(self.get_graph(), path)

    def get_graph(self):
        return self.graph

    def get_copy(self):
        copy_obj = type(self)()
        copy_obj.graph = self.graph.copy()
        copy_obj.root_node = self.root_node  # Node references remain the same.
        copy_obj.time_source = self.time_source
        copy_obj.property_textual_representation = self.property_textual_representation
        return copy_obj

    def get_property_textual_representation(self):
        return self.property_textual_representation if self.property_textual_representation else ""

    def set_property_textual_representation(self, textual_representation):
        self.property_textual_representation = textual_representation

    def get_leaves(self):
        return [n for n, d in self.graph.out_degree() if d == 0]

    def get_present_time_subgraph(self):
        present_time_edges = [(e[0], e[1]) for e in self.graph.edges(data=TIMESTAMP_PROPERTY_NAME)
                              if e[2].matches(Timestamp(self.time_source.get_current_time()))]
        subgraph = self.graph.edge_subgraph(present_time_edges).copy()
        # TODO: Fix subgraph by removing AND nodes with single out edge and adjacent NOT nodes.
        return self._inflate_property_graph_from_subgraph(subgraph)

    def is_implication_graph(self):
        return isinstance(self.root_node, ImplicationOperator) and \
               self.graph.out_degree(self.root_node) > 1

    def visualize(self, title="", show_colorization=False):
        plt.figure(num=None, figsize=(18, 18), dpi=80, facecolor='w', edgecolor='w')
        plt.title(title, fontsize=22, fontweight='bold')
        plt.axis('off')
        plt.tight_layout()
        pos = networkx.nx_agraph.graphviz_layout(self.graph, prog='dot')
        edge_labels = {
            e: str(self.graph.edges[e[0], e[1]][TIMESTAMP_PROPERTY_NAME])
            for e in self.graph.edges
        }
        edge_colors = {
            e: 'red' if self.graph.is_edge_colorized(e[0], e[1]) else 'black'
            for e in self.graph.edges
        }
        node_labels = {
            n: n.get_operator_symbol() if isinstance(n, LogicalOperator) else str(n)
            for n in self.graph.nodes
        }
        draw_networkx(self.graph, pos=pos, font_size=18, node_size=5000,
                      labels=node_labels, font_weight='bold')
        if show_colorization:
            draw_networkx_edges(self.graph, pos=pos, edgelist=list(edge_colors.keys()),
                                edge_color=list(edge_colors.values()))
        draw_networkx_edge_labels(self.graph, pos=pos, edge_labels=edge_labels,
                                  font_size=18, font_color='red')
        plt.show()

    def find_equivalent_subgraphs(self, other):
        matched_paths, matching_groups, found = self._find_equivalent_path_structure(other)
        if not found:
            return [], [], [], []

        original_timestamps = [_find_path_timestamp(p) for p in matched_paths]
        groups_timestamps = [[_find_path_timestamp(p) for p in group] for group in matching_groups]
        cases = list(itertools.product(*matching_groups))  # all subgraphs that match other graph
        cases_timestamps = list(itertools.product(*groups_timestamps))
        sorted_by_original_timestamps = list(zip(*sorted(zip(
            original_timestamps, matched_paths, *cases_timestamps, *cases), key=lambda row: row[0]
        )))
        original_timestamps = sorted_by_original_timestamps[0]
        matched_paths = sorted_by_original_timestamps[1]
        cases_timestamps = sorted_by_original_timestamps[2:len(cases)+2]
        cases = sorted_by_original_timestamps[len(cases)+2:]

        cases_to_remove = set()

        for i in range(len(cases)):
            case = cases[i]
            case_timestamps = cases_timestamps[i]

            if not timestamp_sequences_matches(original_timestamps, case_timestamps):
                cases_to_remove.add(i)

        return [cases[i] for i in range(len(cases)) if i not in cases_to_remove], matched_paths, \
            original_timestamps, cases_timestamps

    def _add_node(self, node):
        self.graph.add_node(node)
        if self.root_node is None:
            self.root_node = node

    def _add_edge(self, start_node, end_node, data_dict=dict()):
        data_dict = {k: v for k, v in data_dict.items() if v}  # Remove None arguments.
        self.graph.add_edge(start_node, end_node, **data_dict)
        if self.get_root_node() is None or end_node == self.get_root_node():
            self.root_node = start_node

    def _inflate_property_graph_from_subgraph(self, subgraph):
        property_graph = TimedPropertyGraph()
        property_graph.graph = subgraph
        property_graph.time_source = self.time_source
        property_graph.property_textual_representation = self.property_textual_representation
        for node_in_degree in subgraph.in_degree():
            if node_in_degree[1] == 0:
                property_graph.root_node = node_in_degree[0]
        if not property_graph.root_node:
            raise Exception("Provided subgraph doesn't contain any root node.")
        return property_graph

    def _find_equivalent_path_structure(self, other):
        """Finds all paths in current graph that combined logically forms the other graph.

        If a logical matching subgraph of other graph is found in current graph, returns all
        paths in current graph, that when combined together, logically forms the other graph.

        Parameters:
            :other: A TimedPropertyGraph object to be logically matched in current object.

        Returns:
            :matched_paths: A list of all the paths contained in other graph, from node to root
                    when a logically matching subgraph of other graph has been found
                    in current graph, else an empty list.
            :matching_groups: A list containing a list of logically matching paths in current
                    graph, for every path contained in matched_paths upon success, otherwise
                    an empty list.
            :found: True when a logically matching subgraph of other graph has been found
                    in current graph, otherwise False.
        """

        # Check that all leaves of other graph, are also leaves of current one.
        other_leaves = other.get_leaves()
        for leaf in other_leaves:
            if not self.get_graph().has_node(leaf):
                return [], [], False

        # Obtain all simple paths from root to leaves in other graph.
        other_paths = all_simple_edge_paths(other.get_graph(), other.get_root_node(), other_leaves)
        # Networkx doesn't include edge data, so manually add timestamps.
        other_paths = _fill_paths_with_timestamps(other.get_graph(), other_paths)

        # Obtain all simple paths from root to leaves of other graph in current graph.
        current_paths = all_simple_edge_paths(self.get_graph(), self.get_root_node(), other_leaves)
        current_paths = list(_fill_paths_with_timestamps(self.get_graph(), current_paths))

        # Find the paths in current graph that logically matches every path of other graph.
        matched_paths = []
        matching_groups = []
        for other_path in other_paths:
            matchings_paths = []
            for cur_path in current_paths:
                if _paths_logically_match(cur_path, other_path):
                    matchings_paths.append(cur_path)
            if not matchings_paths:
                return [], [], False
            matched_paths.append(other_path)
            matching_groups.append(matchings_paths)

        return matched_paths, matching_groups, True

    def _logically_remove_path_set(self, paths):
        for p in paths:
            self.graph.colorize_path(p)
        self.graph.build_colorization_scheme()
        self.graph.disconnect_fully_colorized_sub_dag()


class PredicateGraph(TimedPropertyGraph):
    # TODO: Name predicate nodes using their children too, to not be treated equal.
    def __init__(self, predicate, *args):
        super().__init__()

        # Build predicate node first, so hash doesn't change. Implement it better later.
        self._predicate_node = PredicateNode(predicate)
        for arg in args:
            self._predicate_node.add_argument(arg)

        self._add_node(self._predicate_node)
        for arg in args:
            self._add_argument(arg)

    def _add_argument(self, argument):
        self._add_edge(self._predicate_node, argument)


class PredicateNode:
    def __init__(self, predicate):
        self.predicate = predicate
        self.arguments = []

    def add_argument(self, argument):
        self.arguments.append(argument)
        # self.arguments.sort()

    def __str__(self):
        str_repr = "{}({})".format(
            self.predicate.__str__(), ",".join([arg.__str__() for arg in self.arguments]))
        str_repr = str_repr.replace(" ", "_")
        return str_repr

    def __hash__(self):
        return hash(self.__str__())

    def __eq__(self, other):
        if isinstance(other, PredicateNode):
            return self.__str__() == other.__str__()
        else:
            return None

    def __repr__(self):
        return self.__str__()


class MonitoredVariable:
    # TODO: Make a registrar so monitored variables with the same name, are the same
    # object in memory too, also encasuplating the real variable.
    def __init__(self, monitored_variable):
        self.monitored_variable = monitored_variable

    def __str__(self):
        return self.monitored_variable

    def __hash__(self):
        return hash(self.monitored_variable)

    def __eq__(self, other):
        try:
            return self.monitored_variable == other.monitored_variable
        except AttributeError:
            return False

    def __repr__(self):
        return self.monitored_variable


class TimestampedPath:
    def __init__(self, path, timestamp):
        self.path = path
        self.timestamp = timestamp


def _get_leaf_nodes(property_graph):
    leaf_nodes = list()
    for node, deg in property_graph.get_graph().out_degree():
        if deg == 0:
            leaf_nodes.append(node)
    return leaf_nodes


def _find_path_to_upper_non_and_nodes(property_graph, start_node):
    graph = property_graph.get_graph()
    paths = []
    for in_edge in graph.in_edges(start_node, data=TIMESTAMP_PROPERTY_NAME):
        if not isinstance(in_edge[0], AndOperator):
            paths.append([in_edge])
        else:
            upper_paths = _find_path_to_upper_non_and_nodes(
                property_graph, in_edge[0])
            for p in upper_paths:
                paths.append([in_edge, *p])
    return paths


def _find_clean_paths_to_root(property_graph, start_node):
    graph = property_graph.get_graph()
    paths = []
    for in_edge in graph.in_edges(start_node, data=TIMESTAMP_PROPERTY_NAME):
        if isinstance(in_edge[0], AndOperator):
            upper_paths = _find_clean_paths_to_root(property_graph, in_edge[0])
            for p in upper_paths:
                paths.append([in_edge, *p])
    return paths


def _find_path_timestamp(path):
    path_timestamp = path[0][2]
    for edge in path:
        path_timestamp = min(path_timestamp, edge[2])
    return path_timestamp


def _edges_match(e1, e2):
    if e1[0] != e2[0]:
        return False
    if e1[1] != e2[1]:
        return False
    if len(e1) > 2 and len(e2) > 2:
        if isinstance(e1[2], Timestamp) and isinstance(e2[2], Timestamp):
            if not e1[2].matches(e2[2]):
                return False
        else:
            raise Exception("Edge comparison without solely timestamp data, not implemented yet.")
    return True


def _fill_paths_with_timestamps(graph, paths):
    for p in paths:
        yield [(u, v, graph.get_edge_data(u, v)[TIMESTAMP_PROPERTY_NAME]) for u, v in p]


def _paths_logically_match(path1, path2):
    # Make sure that both paths are either positive or negative.
    if (_count_nots_in_path(path1) % 2) != (_count_nots_in_path(path2) % 2):
        return False

    # # Make sure that timestamps in both paths match.
    # if not _find_path_timestamp(path1).matches(_find_path_timestamp(path2)):
    #     return False

    def _is_skipable_node(node):
        return isinstance(node, AndOperator) or isinstance(node, NotOperator) \
               or isinstance(node, ImplicationOperator)

    cur_node_1 = path1[-1][1]  # start checking from the end
    cur_node_2 = path2[-1][1]
    if cur_node_1 != cur_node_2:
        return False

    index_1 = len(path1) - 1
    index_2 = len(path2) - 1
    while index_1 >= 0:
        cur_node_1 = path1[index_1][0]
        index_1 -= 1
        if _is_skipable_node(cur_node_1):
            continue

        cur_node_2 = path2[index_2][0]
        index_2 -= 1
        while index_2 >= 0 and _is_skipable_node(cur_node_2):
            cur_node_2 = path2[index_2][0]
            index_2 -= 1

        if not ((isinstance(cur_node_1, LogicalOperator) and isinstance(cur_node_2, LogicalOperator)
                 and cur_node_1.logically_matches(cur_node_2)) or cur_node_1 == cur_node_2):
            return False

    return True


def _count_nots_in_path(path):
    all_nots = [e[0] for e in path if isinstance(e[0], NotOperator)]
    if isinstance(path[-1][1], NotOperator):
        all_nots.append(path[-1][1])
    return len(all_nots)