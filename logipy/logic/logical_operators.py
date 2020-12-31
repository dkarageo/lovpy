class LogicalOperator:
    def __init__(self, *args):
        args_list = [str(arg) for arg in args]
        if not self.operands_order_matters():
            # Sort the arguments, so their order doesn't matter in string representation.
            args_list.sort()
        # String representation based on the textual representation of operands,
        # is meant to represent two different operators that act on the same operands,
        # in the same way. Later, may consider to use another structure or another
        # hashing function.
        if len(args_list) == 1:
            self.str_representation = self.get_operator_symbol() + args_list[0]
        else:
            self.str_representation = self.get_operator_symbol().join(args_list)

    def __str__(self):
        return self.str_representation

    def __hash__(self):
        return hash(self.str_representation)

    def __repr__(self):
        return self.str_representation

    def operands_order_matters(self):
        return False

    def get_operator_symbol(self):
        raise Exception("Subclass and implement.")


class AndOperator(LogicalOperator):
    def get_operator_symbol(self):
        return "AND"


class NotOperator(LogicalOperator):
    def get_operator_symbol(self):
        return "NOT"


class ImplicationOperator(LogicalOperator):
    def get_operator_symbol(self):
        return "-->"

    def operands_order_matters(self):
        return True
