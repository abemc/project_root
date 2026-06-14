"""
Dynamic Tool Loader: 検証済みPythonファイルを動的にインポートし、
AgentEngine で使用可能な Tool オブジェクトとしてラップ・ロードする。
"""

import importlib.util
import inspect
import logging
import os
import sys
from typing import Dict, Any, Optional
from .agent_engine import Tool, ToolType

logger = logging.getLogger(__name__)


class DynamicToolLoader:
    """自動生成されたツールを動的にインポートし、AgentEngine 互換の Tool オブジェクトにロードする"""

    def __init__(self):
        # ロードされた動的モジュールのキャッシュ
        self.loaded_modules: Dict[str, Any] = {}

    def load_tool_from_file(self, file_path: str, metadata: Dict[str, Any]) -> Tool:
        """
        指定されたファイルパスからPythonモジュールを動的にインポートし、
        エージェント用の Tool オブジェクトを作成する。

        Args:
            file_path: Pythonスクリプトの絶対パス
            metadata: ツールの定義メタデータ (name, description, require_approval など)

        Returns:
            Tool: 動的ロードされ、ラップされた Tool オブジェクト
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Tool file not found at: {file_path}")

        file_name = os.path.basename(file_path)
        module_name = f"dynamic_tool_{file_name.replace('.py', '')}"

        logger.info(f"Loading dynamic tool from {file_path} as module {module_name}")

        try:
            # sys.path にファイルのあるディレクトリを一時的に追加
            dir_path = os.path.dirname(os.path.abspath(file_path))
            if dir_path not in sys.path:
                sys.path.insert(0, dir_path)

            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Failed to create module spec for {file_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # キャッシュに保存
            self.loaded_modules[metadata["name"]] = module

            # 関数オブジェクトの取得
            func_name = metadata["name"]
            if not hasattr(module, func_name):
                raise AttributeError(f"Module {module_name} does not have the function: {func_name}")

            func = getattr(module, func_name)

            # 関数のシグネチャを inspect で解析し、必要な引数リストを取得
            sig = inspect.signature(func)
            required_params = []
            optional_params = []

            for name, param in sig.parameters.items():
                if name in ('self', 'args', 'kwargs'):
                    continue
                if param.default == inspect.Parameter.empty:
                    required_params.append(name)
                else:
                    optional_params.append(name)

            # 既存の ToolType をマッピング（デフォルトは REASONING）
            tool_type_str = metadata.get("tool_type", "reasoning").lower()
            try:
                tool_type = ToolType(tool_type_str)
            except ValueError:
                tool_type = ToolType.REASONING

            # Tool クラスのインスタンスを生成して返す
            tool = Tool(
                name=func_name,
                tool_type=tool_type,
                description=metadata.get("description", func.__doc__ or "動的に生成されたカスタムツールです。"),
                execute_fn=func,
                required_params=required_params,
                optional_params=optional_params,
                require_approval=metadata.get("require_approval", False)
            )

            logger.info(f"Successfully loaded tool: {tool.name} (params: {tool.required_params})")
            return tool

        except Exception as e:
            logger.error(f"Failed to dynamically load tool {metadata.get('name')}: {e}")
            raise RuntimeError(f"Tool dynamic loading failed: {e}")

    def unload_tool(self, tool_name: str) -> bool:
        """
        ロードされた動的ツールモジュールを sys.modules から削除してクリーンアップする。

        Args:
            tool_name: 削除するツール（関数）名

        Returns:
            bool: 成功したかどうか
        """
        module_name = f"dynamic_tool_{tool_name}"
        if module_name in sys.modules:
            del sys.modules[module_name]
        if tool_name in self.loaded_modules:
            del self.loaded_modules[tool_name]
            logger.info(f"Unloaded dynamic tool: {tool_name}")
            return True
        return False
