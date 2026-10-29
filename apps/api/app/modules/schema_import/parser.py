"""Bounded token parser for the documented DDL subset. Never executes SQL."""
from dataclasses import dataclass
import re

from .models import DatabaseSchema, Table, Column, ForeignKey, Check, identity


@dataclass(frozen=True)
class Token:
    kind: str
    value: str


def tokenize(sql):
    """Tokenize PostgreSQL DDL SQL into structured tokens for parsing.
    
    This function handles:
    - Single-line comments (--)
    - Multi-line comments (/* */)
    - Quoted strings (single and double quotes)
    - Identifiers and keywords
    - Numbers and symbols
    - Parenthesis depth tracking
    
    Limits enforced:
    - SQL size: 256 KB UTF-8 bytes
    - Token length: 4096 characters
    - Comment nesting: 32 levels
    """
    if len(sql.encode("utf-8")) > 262144:
        raise ValueError("SQL exceeds 256 KB")
    tokens, i, depth = [], 0, 0
    while i < len(sql):
        c = sql[i]
        if c.isspace():
            i += 1
            continue
        if sql.startswith("--", i):
            end = sql.find("\n", i)
            i = len(sql) if end < 0 else end + 1
            continue
        if sql.startswith("/*", i):
            nesting = 1
            i += 2
            while i < len(sql) and nesting:
                if sql.startswith("/*", i):
                    nesting += 1
                    if nesting > 32:
                        raise ValueError("Comment nesting exceeds 32")
                    i += 2
                elif sql.startswith("*/", i):
                    nesting -= 1
                    i += 2
                else:
                    i += 1
            if nesting:
                raise ValueError("Unterminated SQL comment")
            continue
        if c in "\"'":
            quote, value = c, ""
            i += 1
            while i < len(sql):
                if sql[i] == quote:
                    if i + 1 < len(sql) and sql[i + 1] == quote:
                        value += quote
                        i += 2
                        continue
                    i += 1
                    break
                if sql[i] == "\x00":
                    raise ValueError("NUL is not allowed")
                value += sql[i]
                i += 1
                if len(value) > 4096:
                    raise ValueError("SQL token exceeds 4096 characters")
            else:
                raise ValueError("Unterminated quoted SQL token")
            tokens.append(Token("id" if quote == '"' else "string", value))
        elif c.isascii() and (c.isalpha() or c == "_"):
            match = re.match(r"[A-Za-z_][A-Za-z0-9_$]*", sql[i:])
            value = match.group()
            tokens.append(Token("word", value.lower()))
            i += len(value)
        elif c.isascii() and c.isdigit():
            match = re.match(r"\d+(?:\.\d+)?", sql[i:])
            value = match.group()
            tokens.append(Token("number", value))
            i += len(value)
        elif c in "(),;.+-*/=<>:":
            pair = sql[i:i+2]
            value = pair if pair in {">=", "<=", "<>", "::"} else c
            tokens.append(Token("symbol", value))
            i += len(value)
            if c == "(":
                depth += 1
                if depth > 32:
                    raise ValueError("Parenthesis nesting exceeds 32")
            if c == ")":
                depth -= 1
                if depth < 0:
                    raise ValueError("Unbalanced parentheses")
        else:
            raise ValueError(f"Unsupported SQL character at position {i + 1}")
        if len(tokens) > 40000:
            raise ValueError("SQL exceeds token budget")
    if depth:
        raise ValueError("Unbalanced parentheses")
    return tokens


TYPES = {"integer", "bigint", "smallint", "varchar", "char", "text", "boolean", "date", "timestamp", "timestamptz", "uuid", "numeric", "decimal", "real", "serial", "bigserial"}
ALIASES = {"int": "integer", "int4": "integer", "int8": "bigint", "int2": "smallint", "bool": "boolean", "float4": "real", "float8": "double precision"}
NUMBERS = {"integer", "bigint", "smallint", "serial", "bigserial", "numeric", "decimal", "real", "double precision"}


def mapping(column):
    """Suggest appropriate field generator based on column type and name.
    
    This function maps PostgreSQL column types to synthetic data generators:
    - Serial types -> sequence generators
    - Numeric types -> integer or decimal generators
    - Recognized column names (quantity, price) -> specific generators
    - Text types -> string generators with length constraints
    - Date/timestamp types -> date generators
    - Boolean type -> boolean generator
    - UUID type -> UUID generator
    """
    kind = column["database_type"]
    name = column["name"].lower()
    options = {}
    generator = "string"
    if kind in NUMBERS:
        generator = "integer" if kind in {"integer", "bigint", "smallint"} else "decimal"
        if kind in {"serial", "bigserial"}:
            generator, options = "sequence", {"padding": 0}
        elif name in {"quantity", "price"}:
            generator = name if (name == "price" or generator == "integer") else generator
        args = column.get("type_arguments", [])
        if kind in {"numeric", "decimal"} and args:
            scale = args[1] if len(args) == 2 else 0
            options.update(precision=min(scale, 6), max=min(100, float(10 ** min(args[0] - scale, 10) - 10 ** -min(scale, 6))))
    elif kind == "boolean":
        generator = "boolean"
    elif kind == "uuid":
        generator = "uuid"
    elif kind in {"date", "timestamp", "timestamptz"}:
        generator = "birth_date" if kind == "date" and name == "birth_date" else "date" if kind == "date" else "datetime"
        options = {"format": "%Y-%m-%d" if kind == "date" else "%Y-%m-%dT%H:%M:%S"}
    elif kind == "enum":
        generator, options = "enum", {"values": column["enum_values"]}
    else:
        if name in {"first_name", "last_name", "full_name", "email", "student_id", "phone_number", "city", "school_year"}:
            generator = name
        args = column.get("type_arguments", [])
        if args or kind == "char":
            length = min(args[0] if args else 1, 256)
            options = {"min_length": min(5, length), "max_length": length}
    column.update(synthetic_generator=generator, generator_options=options)
    return column


class Parser:
    def __init__(self, sql):
        self.tokens = tokenize(sql)
        self.i = 0
        self.tables, self.enums, self.warnings = {}, {}, []

    def peek(self, value=None):
        if self.i >= len(self.tokens):
            return False
        token = self.tokens[self.i]
        return token if value is None else token.kind in {"word", "symbol"} and token.value == value

    def accept(self, value):
        if self.peek(value):
            self.i += 1
            return True
        return False

    def require(self, value):
        if not self.accept(value):
            raise ValueError(f"Expected {value!r} near token {self.i + 1}; syntax is malformed or unsupported")

    def take(self):
        token = self.peek()
        if not token:
            raise ValueError("Unexpected end of SQL")
        self.i += 1
        return token

    def identifier(self):
        token = self.take()
        if token.kind not in {"word", "id"} or not token.value or len(token.value.encode("utf-8")) > 63:
            raise ValueError("Expected an identifier of at most 63 UTF-8 bytes")
        return token.value

    def qualified(self):
        first = self.identifier()
        return (first, self.identifier()) if self.accept(".") else ("public", first)

    def columns(self):
        self.require("(")
        result = [self.identifier()]
        while self.accept(","):
            result.append(self.identifier())
        self.require(")")
        return result

    def foreign(self, source):
        target = identity(*self.qualified())
        columns = self.columns() if self.peek("(") else []
        result = dict(source_columns=source, target_table=target, target_columns=columns)
        seen = set()
        while self.accept("on"):
            action = self.take().value
            if action not in {"delete", "update"} or action in seen:
                raise ValueError("Invalid or duplicate foreign-key action")
            seen.add(action)
            token = self.take().value
            if token == "no":
                self.require("action")
                token = "no action"
            elif token == "set":
                suffix = self.take().value
                if suffix not in {"null", "default"}:
                    raise ValueError("Unsupported SET action")
                token += " " + suffix
            if token not in {"no action", "restrict", "cascade", "set null", "set default"}:
                raise ValueError("Unsupported foreign-key action")
            result["on_" + action] = token.upper()
        return result

    def check(self, table):
        self.require("(")
        column = self.identifier()
        operator = self.take().value
        sign = -1 if self.accept("-") else 1
        token = self.take()
        if operator not in {">", ">=", "<", "<=", "=", "<>"} or token.kind != "number":
            raise ValueError("Unsupported CHECK: use a single numeric column comparison to a numeric literal")
        value = float(token.value) * sign
        self.require(")")
        table["checks"].append(dict(column=column, operator=operator, value=value))

    def default_expression(self):
        """Consume only literals and explicitly recognized inert default expressions."""
        if self.accept("("):
            self.default_expression()
            self.require(")")
        else:
            signed = self.accept("-") or self.accept("+")
            token = self.take()
            if signed and token.kind != "number":
                raise ValueError("Signed DEFAULT requires a number")
            if token.kind not in {"number", "string"}:
                if token.kind != "word":
                    raise ValueError("Unsupported DEFAULT expression")
                if token.value in {"now", "gen_random_uuid", "uuid_generate_v4"}:
                    self.require("(")
                    self.require(")")
                elif token.value == "nextval":
                    self.require("(")
                    if self.take().kind != "string":
                        raise ValueError("nextval DEFAULT requires a string literal")
                    if self.accept("::"):
                        self.require("regclass")
                    self.require(")")
                elif token.value not in {"true", "false", "null", "current_timestamp", "current_date"}:
                    raise ValueError("Unsupported DEFAULT expression; use a literal or a documented default function")
        if self.accept("::"):
            self.qualified()

    def constraint(self, table):
        if self.accept("constraint"):
            self.identifier()
        if self.accept("primary"):
            self.require("key")
            if table["primary_key"]:
                raise ValueError("Multiple primary keys")
            table["primary_key"] = self.columns()
        elif self.accept("unique"):
            table["unique_constraints"].append(self.columns())
        elif self.accept("foreign"):
            self.require("key")
            source = self.columns()
            self.require("references")
            table["foreign_keys"].append(self.foreign(source))
        elif self.accept("check"):
            self.check(table)
        else:
            raise ValueError("Unsupported table constraint")

    def column(self, table):
        name = self.identifier()
        token = self.take()
        kind = ALIASES.get(token.value, token.value) if token.kind == "word" else token.value
        enum_key = identity("public", token.value)
        if self.accept("."):
            enum_key = identity(token.value, self.identifier())
            kind = "qualified enum"
        elif token.kind == "word" and kind == "double":
            self.require("precision")
            kind = "double precision"
        elif token.kind == "word" and kind == "character":
            kind = "varchar" if self.accept("varying") else "char"
        enum = self.enums.get(enum_key)
        if enum is not None and (token.kind == "id" or kind not in TYPES | {"double precision"}):
            kind = "enum"
        elif token.kind != "word" or kind not in TYPES | {"double precision"}:
            raise ValueError(f"Unsupported or undeclared column type: {token.value}")
        args = []
        if self.accept("("):
            while True:
                arg = self.take()
                if arg.kind != "number" or not arg.value.isdigit() or len(arg.value) > 8:
                    raise ValueError("Type parameters must be bounded nonnegative integers")
                args.append(int(arg.value))
                if not self.accept(","):
                    break
            self.require(")")
        if kind == "timestamp":
            if self.accept("with"):
                self.require("time")
                self.require("zone")
                kind = "timestamptz"
            elif self.accept("without"):
                self.require("time")
                self.require("zone")
        col = dict(name=name, database_type=kind, type_arguments=args, nullable=kind not in {"serial", "bigserial"})
        if kind == "enum":
            col["enum_values"] = enum
            col["enum_name"] = enum_key
        seen = set()
        while self.peek() and not self.peek(",") and not self.peek(")"):
            if self.accept("constraint"):
                self.identifier()
            clause = self.take()
            if clause.kind != "word" or clause.value in seen:
                raise ValueError("Invalid or duplicate column constraint")
            seen.add(clause.value)
            if clause.value == "primary":
                self.require("key")
                if table["primary_key"]:
                    raise ValueError("Multiple primary keys")
                table["primary_key"] = [name]
            elif clause.value == "unique":
                table["unique_constraints"].append([name])
            elif clause.value == "not":
                if "null" in seen:
                    raise ValueError("Conflicting nullability")
                self.require("null")
                col["nullable"] = False
            elif clause.value == "null":
                if "not" in seen:
                    raise ValueError("Conflicting nullability")
                col["nullable"] = True
            elif clause.value == "references":
                table["foreign_keys"].append(self.foreign([name]))
            elif clause.value == "check":
                self.check(table)
            elif clause.value == "default":
                start = self.i
                self.default_expression()
                parts = self.tokens[start:self.i]
                col["default"] = " ".join(("'" + t.value.replace("'", "''") + "'") if t.kind == "string" else ('"' + t.value.replace('"', '""') + '"') if t.kind == "id" else t.value for t in parts)
                self.warnings.append(f"{table['name']}.{name}: DEFAULT retained as text; synthetic mapping supplies values. Expressions are never evaluated.")
            else:
                raise ValueError(f"Unsupported column clause: {clause.value}")
        table["columns"].append(mapping(col))

    def parse(self, name):
        statements = 0
        while self.peek():
            if self.accept(";"):
                continue
            statements += 1
            if statements > 200:
                raise ValueError("Maximum 200 DDL statements")
            if self.accept("create"):
                if self.accept("type"):
                    key = identity(*self.qualified())
                    if key in self.enums:
                        raise ValueError("Duplicate enum type")
                    self.require("as")
                    self.require("enum")
                    self.require("(")
                    values = []
                    while True:
                        token = self.take()
                        if token.kind != "string":
                            raise ValueError("ENUM requires string literals")
                        values.append(token.value)
                        if not self.accept(","):
                            break
                    self.require(")")
                    if len(values) > 500 or len(set(values)) != len(values) or any(len(v) > 256 for v in values):
                        raise ValueError("Invalid or oversized enum domain")
                    self.enums[key] = values
                else:
                    self.require("table")
                    if self.accept("if"):
                        self.require("not")
                        self.require("exists")
                    schema, table_name = self.qualified()
                    key = identity(schema, table_name)
                    if key in self.tables:
                        raise ValueError("Duplicate table definition")
                    if len(self.tables) >= 20:
                        raise ValueError("Maximum 20 tables")
                    table = dict(name=table_name, schema_name=schema, columns=[], primary_key=[], unique_constraints=[], foreign_keys=[], checks=[])
                    self.require("(")
                    while True:
                        if any(self.peek(k) for k in ("constraint", "primary", "unique", "foreign", "check")):
                            self.constraint(table)
                        else:
                            self.column(table)
                        if len(table["columns"]) > 50:
                            raise ValueError("Maximum 50 columns per table")
                        if not self.accept(","):
                            break
                    self.require(")")
                    self.tables[key] = table
            elif self.accept("alter"):
                self.require("table")
                key = identity(*self.qualified())
                if key not in self.tables:
                    raise ValueError("ALTER TABLE requires a previously declared table")
                self.require("add")
                self.constraint(self.tables[key])
            else:
                raise ValueError("Unsupported statement: only CREATE TABLE, CREATE TYPE AS ENUM and ALTER TABLE ADD constraints are accepted")
            if self.peek():
                self.require(";")
        for table in self.tables.values():
            for column in table["columns"]:
                if column["name"] in table["primary_key"] and column["database_type"] in {"integer", "bigint", "smallint"}:
                    column.update(synthetic_generator="sequence", generator_options={"padding": 0})
            for fk in table["foreign_keys"]:
                if not fk["target_columns"]:
                    target = self.tables.get(fk["target_table"])
                    if not target or not target["primary_key"]:
                        raise ValueError("REFERENCES without columns requires a declared primary key")
                    fk["target_columns"] = target["primary_key"][:]
        self.warnings.append("Mappings use type and name hints; review them before generating. SQL defaults are not generator rules.")
        return DatabaseSchema(name=name, tables=[Table.model_validate(t) for t in self.tables.values()], warnings=self.warnings)


def parse_sql(sql, name="Imported database"):
    return Parser(sql).parse(name)
