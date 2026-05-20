"""
Tools de contexto: save_context, load_context e list_projects.

Persiste o estado de cada projeto em um arquivo Markdown dentro de projects/.
Não usa banco de dados — só I/O de arquivo simples.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path


PROJECTS_DIR = Path(__file__).resolve().parent.parent / "projects"


# Marcador usado para localizar o início do histórico de iterações no arquivo.
HISTORY_HEADER = "## Histórico de iterações"


def _ensure_projects_dir() -> None:
    """Garante que a pasta projects/ existe."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def _atomic_write(path: Path, content: str) -> None:
    """Escreve atomicamente: tempfile no mesmo diretório + os.replace.

    Garante que leitores concorrentes nunca vejam um arquivo parcialmente escrito,
    e que escritas simultâneas não corrompam o conteúdo (a última vence).
    """
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _sanitize_project_name(name: str) -> str:
    """Sanitiza nome de projeto para uso seguro como nome de arquivo.

    Remove caracteres que não sejam alfanuméricos, hífen, underscore ou ponto.
    """
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", name.strip())
    if not sanitized:
        raise ValueError("project_name resulta vazio após sanitização")
    return sanitized


def _project_path(project_name: str) -> Path:
    """Devolve o Path absoluto do arquivo .md do projeto."""
    return PROJECTS_DIR / f"{_sanitize_project_name(project_name)}.md"


def _count_iterations(content: str) -> int:
    """Conta quantas iterações já existem no histórico do arquivo."""
    return len(re.findall(r"^### Iteração \d+", content, flags=re.MULTILINE))


def _build_initial_file(
    project_name: str,
    project_description: str,
    what_was_done: str,
    decisions: str,
    next_steps: str,
    timestamp: str,
) -> str:
    """Monta o conteúdo inicial do arquivo de projeto (primeira iteração)."""
    return (
        f"# Projeto: {project_name}\n\n"
        f"## Descrição\n{project_description or '(sem descrição)'}\n\n"
        f"## Decisões técnicas\n{decisions or '(nenhuma decisão registrada ainda)'}\n\n"
        f"## Estado atual\n{what_was_done}\n\n"
        f"## Próximos passos\n{next_steps or '(nenhum próximo passo registrado)'}\n\n"
        f"{HISTORY_HEADER}\n"
        f"### Iteração 1 — {timestamp}\n"
        f"- **Feito:** {what_was_done}\n"
        f"- **Decisões:** {decisions or '(nenhuma)'}\n"
        f"- **Próximos passos:** {next_steps or '(nenhum)'}\n"
    )


def _update_section(content: str, header: str, new_body: str) -> str:
    """Substitui o corpo de uma seção markdown identificada por seu header.

    Funciona para headers de nível 2 (##). Se a seção não existir, devolve
    o conteúdo original sem modificação.
    """
    # Regex captura o header e tudo até o próximo header de nível 2 ou fim de arquivo.
    pattern = re.compile(
        rf"(^{re.escape(header)}\n)(.*?)(?=^## |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    if not pattern.search(content):
        return content
    return pattern.sub(lambda m: m.group(1) + new_body + "\n\n", content, count=1)


def _append_iteration(
    content: str,
    iteration_num: int,
    timestamp: str,
    what_was_done: str,
    decisions: str,
    next_steps: str,
) -> str:
    """Adiciona uma nova iteração ao final do histórico."""
    new_entry = (
        f"### Iteração {iteration_num} — {timestamp}\n"
        f"- **Feito:** {what_was_done}\n"
        f"- **Decisões:** {decisions or '(nenhuma)'}\n"
        f"- **Próximos passos:** {next_steps or '(nenhum)'}\n"
    )
    # Garante quebra de linha antes do append.
    if not content.endswith("\n"):
        content += "\n"
    return content + new_entry


def _accumulate_decisions(existing: str, new_decisions: str) -> str:
    """Concatena novas decisões às já existentes, sem duplicar.

    Se a seção existente está marcada como placeholder, substitui.
    Senão, adiciona uma nova linha com a decisão nova.
    """
    new_decisions = new_decisions.strip()
    if not new_decisions:
        return existing.strip() or "(nenhuma decisão registrada ainda)"

    existing_clean = existing.strip()
    if not existing_clean or existing_clean == "(nenhuma decisão registrada ainda)":
        return new_decisions

    # Dedup linha-a-linha para evitar falso-positivo por substring.
    existing_lines = {line.lstrip("- ").strip() for line in existing_clean.splitlines() if line.strip()}
    if new_decisions in existing_lines:
        return existing_clean

    return f"{existing_clean}\n- {new_decisions}"


def _extract_section_body(content: str, header: str) -> str:
    """Extrai o corpo (sem o header) de uma seção markdown de nível 2."""
    pattern = re.compile(
        rf"^{re.escape(header)}\n(.*?)(?=^## |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        return ""
    return match.group(1).strip()


def save_context(
    project_name: str,
    what_was_done: str,
    decisions: str = "",
    next_steps: str = "",
    project_description: str = "",
) -> str:
    """Salva ou atualiza o contexto de um projeto.

    Cria projects/{project_name}.md se não existir.
    Caso já exista, atualiza Estado atual e Próximos passos, acumula decisões
    e adiciona uma nova entrada no histórico de iterações.

    Returns:
        Mensagem de confirmação informando o caminho do arquivo e a iteração salva.
    """
    if not project_name or not project_name.strip():
        raise ValueError("project_name não pode estar vazio")
    if not what_was_done or not what_was_done.strip():
        raise ValueError("what_was_done não pode estar vazio")

    _ensure_projects_dir()
    path = _project_path(project_name)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if not path.exists():
            # Primeira vez deste projeto — cria arquivo do zero.
            content = _build_initial_file(
                project_name=project_name,
                project_description=project_description,
                what_was_done=what_was_done,
                decisions=decisions,
                next_steps=next_steps,
                timestamp=timestamp,
            )
            _atomic_write(path, content)
            return (
                f"Contexto do projeto '{project_name}' criado em {path}.\n"
                f"Iteração 1 registrada em {timestamp}."
            )

        # Projeto já existe — lê, atualiza seções e adiciona iteração.
        content = path.read_text(encoding="utf-8")
        iteration_num = _count_iterations(content) + 1

        # Atualiza Estado atual com o que foi feito agora.
        content = _update_section(content, "## Estado atual", what_was_done)

        # Atualiza Próximos passos com o valor mais recente.
        content = _update_section(
            content,
            "## Próximos passos",
            next_steps or "(nenhum próximo passo registrado)",
        )

        # Acumula decisões técnicas em vez de sobrescrever.
        if decisions.strip():
            existing_decisions = _extract_section_body(content, "## Decisões técnicas")
            merged = _accumulate_decisions(existing_decisions, decisions)
            content = _update_section(content, "## Decisões técnicas", merged)

        # Se project_description foi passado e a descrição atual é placeholder, atualiza.
        if project_description.strip():
            existing_desc = _extract_section_body(content, "## Descrição")
            if not existing_desc or existing_desc == "(sem descrição)":
                content = _update_section(content, "## Descrição", project_description)

        # Adiciona a nova entrada ao histórico.
        content = _append_iteration(
            content=content,
            iteration_num=iteration_num,
            timestamp=timestamp,
            what_was_done=what_was_done,
            decisions=decisions,
            next_steps=next_steps,
        )

        path.write_text(content, encoding="utf-8")
        return (
            f"Contexto do projeto '{project_name}' atualizado em {path}.\n"
            f"Iteração {iteration_num} registrada em {timestamp}."
        )

    except OSError as e:
        # I/O quebrou — loga no stderr e re-levanta para o MCP devolver erro ao cliente.
        print(
            f"[mcp-prompt-refiner] erro de I/O ao salvar contexto: {e}",
            file=sys.stderr,
        )
        raise


def load_context(project_name: str) -> str:
    """Carrega o contexto completo de um projeto.

    Returns:
        Conteúdo Markdown do arquivo, ou mensagem indicando que é projeto novo.
    """
    if not project_name or not project_name.strip():
        raise ValueError("project_name não pode estar vazio")

    path = _project_path(project_name)
    if not path.exists():
        return (
            f"Projeto '{project_name}' ainda não tem contexto salvo.\n"
            f"É um projeto novo — use save_context após a primeira iteração."
        )

    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        print(
            f"[mcp-prompt-refiner] erro ao carregar contexto: {e}",
            file=sys.stderr,
        )
        raise


def list_projects() -> str:
    """Lista todos os projetos com contexto salvo.

    Returns:
        Texto formatado com nome do projeto e data da última modificação.
    """
    _ensure_projects_dir()
    files = sorted(PROJECTS_DIR.glob("*.md"))

    if not files:
        return "Nenhum projeto com contexto salvo até o momento."

    lines = ["Projetos com contexto salvo:\n"]
    for f in files:
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            mtime_str = mtime.strftime("%Y-%m-%d %H:%M:%S")
            project_name = f.stem
            lines.append(f"- **{project_name}** — última atualização: {mtime_str}")
        except OSError as e:
            print(
                f"[mcp-prompt-refiner] erro ao ler stat de {f}: {e}",
                file=sys.stderr,
            )
            continue

    return "\n".join(lines)
