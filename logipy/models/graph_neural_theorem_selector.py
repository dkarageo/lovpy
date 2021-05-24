import numpy as np

from logipy.logic.next_theorem_selectors import NextTheoremSelector
from .graph_neural_model import NextTheoremSamplesGenerator, create_three_padded_generators, \
    convert_timedpropertygraph_to_stellargraph
from .io import export_grouped_instance


exported = 0  # Number of next theorem selection processes exported so far.


class GraphNeuralNextTheoremSelector(NextTheoremSelector):
    """A Next Theorem Selector that utilizes Graph Neural Networks based models."""

    def __init__(self, model, nodes_encoder, export=False):
        """
        :param model: A model that accepts as input NextTheoremSamplesGenerator generators.
        :param nodes_encoder: An encoder that encodes nodes of the Graph into feature vectors.
        """
        self.model = model
        self.encoder = nodes_encoder
        self.export = export

    def select_next(self, graph, theorem_applications, goal, previous_applications, label=None):
        global exported

        # TODO: Implement another more robust way to stop in-time.
        # Don't use the last applied theorem.
        used_theorems = \
            [previous_applications[-1].implication_graph] if previous_applications else []
        unused_applications = [t for t in theorem_applications
                               if t.implication_graph not in used_theorems]
        if not unused_applications:
            return None

        current_graph, norm = convert_timedpropertygraph_to_stellargraph(graph, self.encoder)
        goal_graph, _ = convert_timedpropertygraph_to_stellargraph(goal, self.encoder)

        current_generator, goal_generator, next_generator = create_three_padded_generators(
            [current_graph] * len(unused_applications),
            [goal_graph] * len(unused_applications),
            [convert_timedpropertygraph_to_stellargraph(
                t_app.actual_implication, self.encoder, norm)[0] for t_app in unused_applications]
        )

        inference_generator = NextTheoremSamplesGenerator(
            current_generator, goal_generator, next_generator)

        scores = self.model.predict(inference_generator)

        if self.export:
            for i, t_app in enumerate(unused_applications):
                export_grouped_instance(graph, goal, t_app.actual_implication,
                                        f"Predicted Score: {scores[i]}",
                                        goal.property_textual_representation,
                                        label,
                                        exported+1)
            exported += 1

        return unused_applications[np.argmax(scores, axis=0)[0]]
