# extract_from_md.py

import re
import argparse
import os
from pathlib import Path

# Mapeamento de identificadores de linguagem para extensões de arquivo comuns
LANG_EXT_MAP = {
    "python": ".py",
    "py": ".py",
    "javascript": ".js",
    "js": ".js",
    "html": ".html",
    "css": ".css",
    "java": ".java",
    "c": ".c",
    "cpp": ".cpp",
    "c++": ".cpp",
    "csharp": ".cs",
    "go": ".go",
    "rust": ".rs",
    "ruby": ".rb",
    "php": ".php",
    "bash": ".sh",
    "shell": ".sh",
    "sql": ".sql",
    "json": ".json",
    "yaml": ".yaml",
    "yml": ".yml",
    "markdown": ".md",
    "xml": ".xml",
}

def get_file_extension(language_identifier: str) -> str:
    """
    Determina a extensão do arquivo com base no identificador de linguagem do Markdown.
    
    Args:
        language_identifier: A string que segue os ``` (ex: 'python').

    Returns:
        A extensão de arquivo apropriada (ex: '.py') ou '.txt' como padrão.
    """
    if not language_identifier:
        return ".txt"
    
    lang_lower = language_identifier.lower().strip()
    return LANG_EXT_MAP.get(lang_lower, f".{lang_lower}")

def extract_code_from_markdown(markdown_file: Path, output_dir: Path):
    """
    Analisa um arquivo Markdown, extrai todos os blocos de código e os salva em arquivos.

    Args:
        markdown_file: O caminho para o arquivo Markdown de entrada.
        output_dir: O diretório onde os arquivos de código extraído serão salvos.
    """
    if not markdown_file.is_file():
        print(f"Erro: O arquivo de entrada não foi encontrado em '{markdown_file}'")
        return

    print(f"Lendo o arquivo: {markdown_file}")
    
    # Cria o diretório de saída se ele não existir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        content = markdown_file.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Erro ao ler o arquivo: {e}")
        return

    # Expressão regular para encontrar blocos de código cercados por ```
    # Explicação:
    # ^```(.*?)      # Linha que começa com ```, capturando a linguagem (não-guloso)
    # \n            # Uma quebra de linha
    # (.*?)         # O conteúdo do código (qualquer caractere, não-guloso)
    # \n            # Uma quebra de linha
    # ^```          # Linha que começa com ``` para fechar o bloco
    # re.DOTALL     # Permite que '.' corresponda a quebras de linha (para o bloco de código)
    # re.MULTILINE  # Permite que '^' corresponda ao início de cada linha
    code_block_pattern = re.compile(r"^```(.*?)\n(.*?)\n^```", re.DOTALL | re.MULTILINE)

    matches = code_block_pattern.findall(content)

    if not matches:
        print("Nenhum bloco de código encontrado no arquivo.")
        return

    print(f"Encontrados {len(matches)} blocos de código. Extraindo para '{output_dir}'...")

    for i, (language, code) in enumerate(matches):
        # Remove espaços em branco desnecessários no início/fim do código
        code = code.strip()

        # Determina a extensão do arquivo
        extension = get_file_extension(language)
        
        # Gera um nome de arquivo único para cada bloco
        base_filename = markdown_file.stem # Nome do arquivo original sem extensão
        output_filename = f"{base_filename}_bloco_{i + 1}{extension}"
        output_path = output_dir / output_filename

        try:
            output_path.write_text(code, encoding="utf-8")
            print(f"  -> Salvo '{output_filename}'")
        except Exception as e:
            print(f"  -> Erro ao salvar '{output_filename}': {e}")
            
    print("\nExtração concluída com sucesso!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extrai blocos de código de um arquivo Markdown e os salva em arquivos separados.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        "markdown_file",
        type=str,
        help="O caminho para o arquivo Markdown de entrada (.md)."
    )
    
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="codigo_extraido",
        help="O diretório de saída para salvar os arquivos de código. (Padrão: 'codigo_extraido')"
    )

    args = parser.parse_args()

    # Usando pathlib para um manuseio de caminhos mais robusto
    input_path = Path(args.markdown_file)
    output_path = Path(args.output)
    
    extract_code_from_markdown(input_path, output_path)