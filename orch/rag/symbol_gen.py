"""SymbolGenerator — Level 3 symbol explanation via tree-sitter + Ollama."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from tree_sitter_languages import get_language

from orch.db.models import Project

if TYPE_CHECKING:
    import tree_sitter
    from sqlalchemy.orm import Session

    from orch.rag.config import CodeUnderstandingConfig


class SymbolGenerator:
    """Generates natural-language explanations of code symbols using tree-sitter and Ollama.

    Parses the source file with tree-sitter to extract the exact source span for the
    requested symbol, then sends the snippet to Ollama for explanation. Falls back to
    the full file content if parsing or symbol extraction fails.

    Attributes:
        LANGUAGE_EXTENSIONS: Mapping of file extensions to tree-sitter language names.
        SYMBOL_KINDS: Tree-sitter node types treated as named symbols.
    """

    LANGUAGE_EXTENSIONS: dict[str, str] = {
        ".py": "python",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".h": "cpp",
        ".hpp": "cpp",
        ".js": "javascript",
        ".ts": "typescript",
        ".rs": "rust",
        ".go": "go",
    }

    SYMBOL_KINDS: set[str] = {
        "function_definition",
        "class_definition",
        "function_item",
        "impl_item",
        "method_declaration",
    }

    async def explain_symbol(
        self,
        project_id: str,
        file_path: str,
        symbol_name: str | None,
        config: CodeUnderstandingConfig,
        session: Session,
    ) -> str:
        """Generate an Ollama explanation for a symbol (or whole file) in the project.

        Args:
            project_id: Project whose repo_root is used to resolve the file path.
            file_path: Path relative to the project repo root.
            symbol_name: Name of the function or class to explain; when None, the
                entire file is explained.
            config: LLM model and Ollama connection settings.
            session: Active SQLAlchemy session for loading the Project row.

        Returns:
            Plain-text explanation produced by the LLM.

        Raises:
            ValueError: If the project does not exist in the database.
            FileNotFoundError: If the resolved file path does not exist on disk.
        """
        project = session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project '{project_id}' not found")

        repo_root = project.repo_root
        absolute_path = Path(repo_root) / file_path

        if not absolute_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_content = absolute_path.read_text(encoding="utf-8", errors="replace")

        if symbol_name is not None:
            source = self._extract_symbol(file_content, file_path, symbol_name)
        else:
            source = file_content

        prompt = self._build_prompt(file_path, symbol_name, source)
        return await self._call_ollama(prompt, config)

    def _extract_symbol(self, file_content: str, file_path: str, symbol_name: str) -> str:
        suffix = Path(file_path).suffix.lower()
        language = self.LANGUAGE_EXTENSIONS.get(suffix)

        if language is None:
            return file_content

        try:
            import tree_sitter

            lang = get_language(language)
            parser = tree_sitter.Parser()
            parser.language = lang
            tree = parser.parse(bytes(file_content, "utf-8"))

            node = self._find_symbol_node(tree.root_node, symbol_name, language)
            if node is not None:
                return self._node_to_text(file_content, node)
        except Exception:  # noqa: S110
            pass

        return file_content

    def _find_symbol_node(
        self, root: tree_sitter.Node, symbol_name: str, language: str
    ) -> tree_sitter.Node | None:
        queue = list(root.children)
        while queue:
            node = queue.pop(0)
            if node.type in self.SYMBOL_KINDS:
                name_node = self._get_name_node(node, language)
                if name_node and name_node.text and name_node.text.decode("utf-8") == symbol_name:
                    return node
            queue.extend(node.children)
        return None

    def _get_name_node(self, node: tree_sitter.Node, language: str) -> tree_sitter.Node | None:
        if language in ("python", "cpp", "c", "javascript", "typescript", "rust", "go"):
            for child in node.children:
                if child.type == "identifier":
                    return child
        return None

    def _node_to_text(self, file_content: str, node: tree_sitter.Node) -> str:
        start_byte = node.start_byte
        end_byte = node.end_byte
        return file_content[start_byte:end_byte]

    def _build_prompt(self, file_path: str, symbol_name: str | None, source: str) -> str:
        """Build the Ollama explanation prompt for a symbol or file.

        Args:
            file_path: Relative file path shown as context in the prompt.
            symbol_name: Symbol name used in the opening line; when None, file_path is used.
            source: The source code snippet or full file content to explain.

        Returns:
            Formatted prompt string ready to send to the LLM.
        """
        target = symbol_name if symbol_name else file_path
        return f"""Explain what {target} does:

```{file_path}
{source}
```

Provide a clear, concise explanation focusing on:
- What the code does
- Key parameters or members
- Any important behavior or side effects
"""

    async def _call_ollama(self, prompt: str, config: CodeUnderstandingConfig) -> str:
        model = config.resolved_llm_model()
        ollama_url = config.ollama_url

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ollama_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            data: dict[str, str] = response.json()
            result: str = data.get("response", "")
            return result
