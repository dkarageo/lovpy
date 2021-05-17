import logging
from enum import Enum
from pathlib import Path

from logipy.logic.next_theorem_selectors import set_default_theorem_selector, \
    BetterNextTheoremSelector
import logipy.graphs
import logipy.models
import logipy.logic.prover
from logipy.models.neural_theorem_selector import NeuralNextTheoremSelector
from logipy.models.graph_neural_theorem_selector import GraphNeuralNextTheoremSelector
from logipy.models.io import load_gnn_model


LOGIPY_ROOT_PATH = Path(__file__).absolute().parent  # Absolute path of logipy's installation.

LOGGER_NAME = "logipy"

# Attributes controlling graph visualization.
SCRATCHDIR_PATH = LOGIPY_ROOT_PATH.parent / "_temp/"
GRAPHVIZ_OUT_FILE = 'temp_graphviz_out.png'

# Attributes controlling models module.
MODELS_DIR = "models"
USE_NEURAL_SELECTOR = True
# Constants for simple NN model.
MAIN_MODEL_NAME = "main_model"
PREDICATES_MAP_NAME = "main_model_predicates.json"
# Constants for DGCNN model.
GRAPH_MODEL_NAME = "gnn_model"
GRAPH_ENCODER_NAME = "graph_nodes_encoder"
# Constants for sample visualization.
CURRENT_GRAPH_FILENAME = "temp_current.jpg"
GOAL_GRAPH_FILENAME = "temp_goal.jpg"
NEXT_GRAPH_FILENAME = "temp_next.jpg"


class TheoremSelector(Enum):
    """An Enum that defines all available theorem selectors in logipy."""
    DETERMINISTIC = 1
    SIMPLE_NN = 2
    DGCNN = 3


def get_scratchfile_path(filename):
    """Returns absolute path of a file with given filename into logipy's scratchdir.

    If scratchdir doesn't exist, it is created first.
    """
    if not SCRATCHDIR_PATH.exists():
        SCRATCHDIR_PATH.mkdir()
    return SCRATCHDIR_PATH / filename


def remove_scratchfile(filename):
    """Removes given file from logipy's scratchdir.

    If removing the file empties scratchdir, scratchdir is also removed.
    """
    absolute_scratchfile_path = SCRATCHDIR_PATH / filename
    if Path(absolute_scratchfile_path).is_file():
        absolute_scratchfile_path.unlink()
    if SCRATCHDIR_PATH.is_dir() and not any(SCRATCHDIR_PATH.iterdir()):
        SCRATCHDIR_PATH.rmdir()


def get_models_dir_path(filename=None):
    """Returns absolute path of the models directory.

    :param filename: A filename to be appended to models directory path.

    :return: A pathlib's Path object pointing to the absolute path of models' directory when
            filename is not provided. If filename is provided, Path points to the absolute path
            of a file with given filename, inside models' directory.
    """
    absolute_path = Path(__file__).absolute().parent.parent / MODELS_DIR
    if not absolute_path.exists():
        absolute_path.mkdir()
    if filename:
        absolute_path = absolute_path / filename
    return absolute_path


def set_theorem_selector(theorem_selector: TheoremSelector):
    """Sets logipy prover's theorem selector to the given one.

    :return: True if requested theorem selector set successfully. In case of an error,
            e.g. when a trained model does not exist for neural selectors, it returns
            False.
    """
    logger = logging.getLogger(LOGGER_NAME)

    if theorem_selector is TheoremSelector.DETERMINISTIC:
        logger.info("Setting theorem prover to the deterministic one.")
        set_default_theorem_selector(BetterNextTheoremSelector())

    elif theorem_selector is TheoremSelector.SIMPLE_NN:
        logger.info("Setting theorem prover to the simple neural one.")
        set_default_theorem_selector(NeuralNextTheoremSelector())

    elif theorem_selector is TheoremSelector.DGCNN:
        model, encoder = load_gnn_model()
        if model:
            logger.info("Setting theorem prover to the graph neural one.")
            set_default_theorem_selector(GraphNeuralNextTheoremSelector(model, encoder))
        else:
            logger.warning(
                f"Logipy: No model found under {str(get_models_dir_path(GRAPH_MODEL_NAME))}")
            return False
    return True


def is_neural_selector_enabled():
    return USE_NEURAL_SELECTOR


def enable_full_visualization():
    """Enables visualization of proving process."""
    logipy.logic.prover.full_visualization_enabled = True


def tearup_logipy():
    """Initializes logipy's modules."""
    _tearup_graphs_module()
    _tearup_models_module()


def teardown_logipy():
    """Frees up resources allocated by logipy's modules."""
    _teardown_models_module()


def _tearup_graphs_module():
    logipy.graphs.timed_property_graph.graphviz_out_scratchfile_path = \
        get_scratchfile_path(GRAPHVIZ_OUT_FILE)


def _teardown_graphs_module():
    remove_scratchfile(get_scratchfile_path(GRAPHVIZ_OUT_FILE))


def _tearup_models_module():
    # Set model paths.
    logipy.models.io.main_model_path = get_models_dir_path(MAIN_MODEL_NAME)
    logipy.models.io.predicates_map_path = get_models_dir_path(PREDICATES_MAP_NAME)
    logipy.models.io.graph_model_path = get_models_dir_path(GRAPH_MODEL_NAME)
    logipy.models.io.graph_encoder_path = get_models_dir_path(GRAPH_ENCODER_NAME)
    # Set scratch files paths for visualization.
    logipy.models.io.current_graph_path = get_scratchfile_path(CURRENT_GRAPH_FILENAME)
    logipy.models.io.goal_graph_path = get_scratchfile_path(GOAL_GRAPH_FILENAME)
    logipy.models.io.next_graph_path = get_scratchfile_path(NEXT_GRAPH_FILENAME)


def _teardown_models_module():
    # Cleanup scratch files.
    remove_scratchfile(get_models_dir_path(CURRENT_GRAPH_FILENAME))
    remove_scratchfile(get_models_dir_path(GOAL_GRAPH_FILENAME))
    remove_scratchfile(get_models_dir_path(NEXT_GRAPH_FILENAME))
