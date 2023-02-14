from lark import Lark, Transformer
import re
import pandas as pd


grammar = r"""
?start: expression
expression: disjunction
| conjunction
| operation
disjunction: conjunction ("or" conjunction)+ | conjunction
conjunction: group ("and" group)+ | group
group : "(" disjunction ")" | operation
operation : nil | match | equal | notequal
nil : "no" STRING
match : STRING "match" STRING
equal : STRING "=" STRING
notequal: STRING "!=" STRING

%import common.ESCAPED_STRING -> STRING
%import common.WS
%ignore WS
"""


class KernelModuleListFilter (Transformer):
    def __init__(self):
        super().__init__()
        self.operators = []

    def equal(self, vals):
        val = "equal %s = %s" % (vals[0], vals[1])
        self.operators.append(val)

    def notequal(self, vals):
        val = "ne %s = %s" % (vals[0], vals[1])
        self.operators.append(val)

    def match(self, vals):
        val = "match %s = %s" % (vals[0], vals[1])
        self.operators.append(val)

    def nil(self, vals):
        val = "no %s" % vals[0]
        self.operators.append(val)

    def conjunction(self, vals):
        if len(vals) > 1:
            self.operators.append("and")

    def disjunction(self, vals):
        if len(vals) > 1:
            self.operators.append("or")


def km_filter(filter, data):
    if filter == "":
        return data

    parser = Lark(grammar)
    kmf = KernelModuleListFilter()
    tree = parser.parse(filter)
    kmf.transform(tree)

    return KM_filter(kmf.operators, data).process()


class KM_filter:
    def __init__(self, operators, data):
        self._operators = operators
        self.data = data.copy()

    def _foramt_value(val: str):
        val = val.strip()

        # remove '"' from left and right.
        return val[1:len(val)-1]

    def _split_operator(operator: str):
        if operator.startswith("equal"):
            eq = operator[operator.find(" "):]
            vals = eq.split("=")
            flag, value = vals[0], "=".join(vals[1:])
            return [
                        "equal",
                        KM_filter._foramt_value(flag),
                        KM_filter._foramt_value(value)
                    ]
        if operator.startswith("ne"):
            eq = operator[operator.find(" "):]
            vals = eq.split("=")
            flag, value = vals[0], "=".join(vals[1:])
            return [
                        "ne",
                        KM_filter._foramt_value(flag),
                        KM_filter._foramt_value(value)
                    ]
        elif operator.startswith("match"):
            eq = operator[operator.find(" "):]
            vals = eq.split("=")
            flag, value = vals[0], "=".join(vals[1:])
            return [
                        "match",
                        KM_filter._foramt_value(flag),
                        KM_filter._foramt_value(value)
                    ]
        elif operator.startswith("no"):
            flag = operator[operator.find(" "):]
            return ["no", KM_filter._foramt_value(flag)]
        elif operator == "and":
            return ["and"]
        elif operator == "or":
            return ["or"]

        # This should never happen.
        return []

    def _filter(field, oper, value, by_level=False, by_row_level=False):
        if by_row_level:
            field = field["level"]
        elif by_level:
            field = field["level"]["level"]
        else:
            field = field["value"]

        if oper == 'equal':
            if field == value:
                return True
            else:
                return False
        elif oper == 'ne':
            if field != value:
                return True
            else:
                return False
        elif oper == 'match':
            return re.search(value, field) is not None
        elif oper == 'no':
            if field == "":
                return True
            else:
                return False

    def _by_level(field):
        """Check the search is for content or checking result.

        Args:
            field (str): if ended with ".level" means search for checking result.
            otherwise for content.

        Returns:
            str, bool, bool: field, check field level, check row level.
        """
        if field.endswith(".level"):
            field = field[:len(".level")-1]
            if field == "level":
                return field, True, True
            else:
                return field, True, False

        return field, False, False

    def _equal(field, value, df):
        field, by_level, by_row_level = KM_filter._by_level(field)
        return df.loc[df[f"{field}"].apply(
                                            KM_filter._filter,
                                            oper='equal',
                                            value=value,
                                            by_level=by_level,
                                            by_row_level=by_row_level
                                            )]

    def _ne(field, value, df):
        field, by_level, by_row_level = KM_filter._by_level(field)
        return df.loc[df[f"{field}"].apply(
                                            KM_filter._filter,
                                            oper='ne',
                                            value=value,
                                            by_level=by_level,
                                            by_row_level=by_row_level
                                            )]

    def _match(field, value, df):
        return df.loc[df[f"{field}"].apply(
                                            KM_filter._filter,
                                            oper='match',
                                            value=value
                                            )]

    def _no(field, df):
        return df.loc[df[f"{field}"].apply(
                                            KM_filter._filter,
                                            oper='no',
                                            value=""
                                            )]

    def _or(lval, rval):
        pd.merge(lval, rval, how="outer")

    def _and(lval, rval):
        pd.merge(lval, rval, how="inner")

    def process(self):
        """
        Rules (operation: eq, ne, nil, match): 
         1. Operate with the original df if it's an operation.
         2. Remove the operation once it's been used by 'and' or 'or' and save the result (dataframe) by rewriting the value of 'and' or 'or'
         3. if the 'and' or 'or' is the last one but still have others in front, use it to do with the rest from end to front.
        """

        def _last_oper(procs):
            for i in range(len(procs) - 1, -1, -1):
                if procs[i] != "processed":
                    return i
            # This should never happend
            return -1

        last_oper = ""
        proc_lst = []
        opers = self._operators.copy()
        for i in range(0, len(opers)):
            oper = KM_filter._split_operator(opers[i])
            if oper[0] == "equal":
                df = KM_filter._equal(oper[1], oper[2], self.data)
                proc_lst.append(df)
            elif oper[0] == "ne":
                df = KM_filter._ne(oper[1], oper[2], self.data)
                proc_lst.append(df)
            elif oper[0] == "match":
                df = KM_filter._match(oper[1], oper[2], self.data)
                proc_lst.append(df)
            elif oper[0] == "no":
                df = KM_filter._no(oper[1], self.data)
                proc_lst.append(df)
            elif oper[0] == "and":
                last_oper = oper[0]
                val_idx = _last_oper(proc_lst)
                lval = proc_lst[val_idx]
                proc_lst[val_idx] = "processed"
                val_idx = _last_oper(proc_lst)
                rval = proc_lst[val_idx]
                proc_lst[val_idx] = "processed"
                df = KM_filter._and(lval, rval)
                proc_lst.append(df)
            elif oper[0] == "or":
                last_oper = oper[0]
                val_idx = _last_oper(proc_lst)
                lval = proc_lst[val_idx]
                proc_lst[val_idx] = "processed"
                val_idx = _last_oper(proc_lst)
                rval = proc_lst[val_idx]
                proc_lst[val_idx] = "processed"
                df = KM_filter._or(lval, rval)
                proc_lst.append(df)

            last_val_idx = len(proc_lst) - 1
            last_val = proc_lst[last_val_idx]
            for i in range(len(proc_lst)-2, -1 , -1):
                if proc_lst[i] != "processed":
                    val_idx = _last_oper(proc_lst[:len(proc_lst)-2])
                    val = proc_lst[val_idx]
                    proc_lst[val_idx] = "processed"
                    if last_oper == "and":
                        proc_lst[last_val_idx] = KM_filter._and(last_val, val)
                    elif last_oper == "or":
                        proc_lst[last_val_idx] = KM_filter._or(last_val, val)

        return proc_lst[last_val_idx]
