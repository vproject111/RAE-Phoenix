# Copyright 2025 Grzegorz Leśniowski
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from abc import ABC, abstractmethod
from typing import Any

try:
    import escodegen
    import esprima
except ImportError:
    escodegen = None
    esprima = None

# Define a generic ASTNode type for type hinting
ASTNode = Any


class BaseLanguagePlugin(ABC):
    """
    Abstract base class for language-specific plugins.
    Defines the interface for parsing, finding matches, and generating code.
    """

    @abstractmethod
    def parse(self, content: str) -> ASTNode:
        """
        Parses the given code content into an Abstract Syntax Tree (AST).

        :param content: The source code as a string.
        :return: The root node of the AST.
        """
        pass

    @abstractmethod
    def generate(self, ast: ASTNode) -> str:
        """
        Generates source code from an AST.

        :param ast: The root node of the AST.
        :return: The generated source code as a string.
        """
        pass

    @abstractmethod
    def find_matches(self, pattern: dict, ast: ASTNode) -> list[ASTNode]:
        """
        Finds nodes in the AST that match a given pattern.

        :param pattern: The pattern to match.
        :param ast: The root node of the AST to search in.
        """
        pass


class JavaScriptPlugin(BaseLanguagePlugin):
    """
    Language plugin for JavaScript, using esprima and escodegen.
    """

    def parse(self, content: str) -> ASTNode:
        """
        Parses JavaScript code into an AST using esprima.
        """
        if esprima is None:
            raise RuntimeError("esprima package is required for JavaScriptPlugin AST parsing")
        try:
            return esprima.parseScript(content, options={"loc": True, "tolerant": True})
        except esprima.Error as e:
            # Here you might want to log the error or handle it as needed
            raise ValueError(f"Failed to parse JavaScript content: {e}")

    def generate(self, ast: ASTNode) -> str:
        """
        Generates JavaScript code from an AST using escodegen.
        """
        if escodegen is None:
            raise RuntimeError("escodegen package is required for JavaScriptPlugin code generation")
        return escodegen.generate(ast)

    def find_matches(self, pattern: dict, ast: ASTNode) -> list[ASTNode]:
        """
        Finds nodes in the AST that match a given pattern.
        """
        matcher = AstMatcher(pattern)
        matcher.visit(ast)
        return matcher.get_matches()


def _is_node_match(node, pattern_dict: dict) -> bool:
    """Recursively checks if an AST node matches a pattern dictionary."""
    if not node or not isinstance(pattern_dict, dict):
        return False

    for key, pattern_value in pattern_dict.items():
        if not hasattr(node, key):
            return False

        node_value = getattr(node, key)

        if isinstance(pattern_value, dict):
            if not _is_node_match(node_value, pattern_value):
                return False
        elif isinstance(pattern_value, list):
            if not isinstance(node_value, list) or len(node_value) != len(pattern_value):
                return False
            for i, item in enumerate(pattern_value):
                if not _is_node_match(node_value[i], item):
                    return False
        else:
            if node_value != pattern_value:
                return False
    return True


class AstMatcher:
    """Traverses an AST to find all nodes that match the given pattern."""

    def __init__(self, pattern: dict):
        self.pattern = pattern
        self.matches = []

    def visit(self, node):
        if not node:
            return

        if isinstance(node, list):
            for item in node:
                self.visit(item)
            return

        if not hasattr(node, "type"):
            return

        if _is_node_match(node, self.pattern):
            self.matches.append(node)

        # Manually traverse known properties that can contain child nodes
        for prop in [
            "body",
            "expression",
            "callee",
            "object",
            "property",
            "arguments",
            "declarations",
            "init",
            "update",
            "test",
            "consequent",
            "alternate",
            "left",
            "right",
            "elements",
            "id",
            "params",
            "argument",
        ]:
            if hasattr(node, prop):
                child = getattr(node, prop)
                self.visit(child)

    def get_matches(self) -> list[ASTNode]:
        return self.matches
