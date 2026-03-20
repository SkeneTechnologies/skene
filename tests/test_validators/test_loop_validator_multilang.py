"""Integration tests for multi-language validation in loop_validator."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from skene.validators.loop_validator import (
    CheckStatus,
    _extract_names,
    validate_file_requirement,
    validate_function_requirement,
)

# ---------------------------------------------------------------------------
# _extract_names integration
# ---------------------------------------------------------------------------


class TestExtractNames:
    def test_python_file(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text(dedent("""\
            import os
            from pathlib import Path

            class MyService:
                pass

            def handle_request(data):
                pass
        """))
        result = _extract_names(f)
        assert result is not None
        assert "handle_request" in result.functions
        assert "MyService" in result.classes
        assert "os" in result.imports

    def test_typescript_file(self, tmp_path: Path) -> None:
        f = tmp_path / "handler.ts"
        f.write_text(dedent("""\
            import { Request, Response } from 'express';

            export class AuthController {
                async login(req: Request, res: Response): Promise<void> {
                    // ...
                }
            }

            export function validateToken(token: string): boolean {
                return token.length > 0;
            }
        """))
        result = _extract_names(f)
        assert result is not None
        assert "validateToken" in result.functions
        assert "AuthController" in result.classes
        assert "express" in result.imports

    def test_javascript_file(self, tmp_path: Path) -> None:
        f = tmp_path / "utils.js"
        f.write_text(dedent("""\
            const lodash = require('lodash');

            function formatDate(date) {
                return date.toISOString();
            }

            const capitalize = (str) => str.charAt(0).toUpperCase() + str.slice(1);
        """))
        result = _extract_names(f)
        assert result is not None
        assert "formatDate" in result.functions
        assert "capitalize" in result.functions
        assert "lodash" in result.imports

    def test_go_file(self, tmp_path: Path) -> None:
        f = tmp_path / "server.go"
        f.write_text(dedent("""\
            package main

            import "net/http"

            type Router struct {
                routes map[string]http.Handler
            }

            func NewRouter() *Router {
                return &Router{}
            }
        """))
        result = _extract_names(f)
        assert result is not None
        assert "NewRouter" in result.functions
        assert "Router" in result.classes

    def test_unsupported_extension_returns_none(self, tmp_path: Path) -> None:
        f = tmp_path / "config.yaml"
        f.write_text("key: value\n")
        assert _extract_names(f) is None

    def test_nonexistent_file_returns_none(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.ts"
        assert _extract_names(f) is None


# ---------------------------------------------------------------------------
# validate_file_requirement with non-Python files
# ---------------------------------------------------------------------------


class TestValidateFileRequirementMultiLang:
    def test_ts_function_exists_passes(self, tmp_path: Path) -> None:
        ts_file = tmp_path / "integration.ts"
        ts_file.write_text(dedent("""\
            export function integrateWithWordPress(config: WPConfig): void {
                console.log('integrating');
            }
        """))

        req = {
            "path": "integration.ts",
            "purpose": "WordPress integration",
            "required": True,
            "checks": [
                {"type": "function_exists", "pattern": "integrateWithWordPress", "description": "WP function"},
            ],
        }
        result = validate_file_requirement(req, tmp_path)
        assert result.exists is True
        assert len(result.checks) == 1
        assert result.checks[0].status == CheckStatus.PASSED

    def test_ts_function_exists_fails_when_missing(self, tmp_path: Path) -> None:
        ts_file = tmp_path / "integration.ts"
        ts_file.write_text(dedent("""\
            export function otherFunction(): void {}
        """))

        req = {
            "path": "integration.ts",
            "purpose": "WordPress integration",
            "required": True,
            "checks": [
                {"type": "function_exists", "pattern": "integrateWithWordPress", "description": "WP function"},
            ],
        }
        result = validate_file_requirement(req, tmp_path)
        assert result.exists is True
        assert len(result.checks) == 1
        assert result.checks[0].status == CheckStatus.FAILED
        assert "not found" in result.checks[0].detail

    def test_ts_class_exists(self, tmp_path: Path) -> None:
        ts_file = tmp_path / "service.ts"
        ts_file.write_text(dedent("""\
            export class WordPressService {
                constructor(private config: Config) {}
            }
        """))

        req = {
            "path": "service.ts",
            "purpose": "WP service",
            "required": True,
            "checks": [
                {"type": "class_exists", "pattern": "WordPressService", "description": "WP service class"},
            ],
        }
        result = validate_file_requirement(req, tmp_path)
        assert result.checks[0].status == CheckStatus.PASSED

    def test_ts_import_exists(self, tmp_path: Path) -> None:
        ts_file = tmp_path / "app.ts"
        ts_file.write_text(dedent("""\
            import { createClient } from '@supabase/supabase-js';
        """))

        req = {
            "path": "app.ts",
            "purpose": "App entry",
            "required": True,
            "checks": [
                {"type": "import_exists", "pattern": "@supabase/supabase-js", "description": "Supabase import"},
            ],
        }
        result = validate_file_requirement(req, tmp_path)
        assert result.checks[0].status == CheckStatus.PASSED

    def test_contains_still_works_for_ts(self, tmp_path: Path) -> None:
        ts_file = tmp_path / "config.ts"
        ts_file.write_text("export const API_URL = 'https://api.example.com';\n")

        req = {
            "path": "config.ts",
            "purpose": "Config",
            "required": True,
            "checks": [
                {"type": "contains", "pattern": "API_URL", "description": "API URL constant"},
            ],
        }
        result = validate_file_requirement(req, tmp_path)
        assert result.checks[0].status == CheckStatus.PASSED

    def test_unsupported_extension_skips_ast_checks(self, tmp_path: Path) -> None:
        f = tmp_path / "config.yaml"
        f.write_text("functions:\n  - name: test\n")

        req = {
            "path": "config.yaml",
            "purpose": "Config",
            "required": True,
            "checks": [
                {"type": "function_exists", "pattern": "test", "description": "should skip"},
            ],
        }
        result = validate_file_requirement(req, tmp_path)
        assert result.checks[0].status == CheckStatus.SKIPPED
        assert "not supported" in result.checks[0].detail

    def test_mixed_checks_on_ts_file(self, tmp_path: Path) -> None:
        ts_file = tmp_path / "plugin.ts"
        ts_file.write_text(dedent("""\
            import axios from 'axios';

            export class PluginManager {
                register(name: string) {}
            }

            export function initPlugin(): void {}

            const API_KEY = 'secret';
        """))

        req = {
            "path": "plugin.ts",
            "purpose": "Plugin system",
            "required": True,
            "checks": [
                {"type": "function_exists", "pattern": "initPlugin", "description": "init fn"},
                {"type": "class_exists", "pattern": "PluginManager", "description": "manager class"},
                {"type": "import_exists", "pattern": "axios", "description": "HTTP client"},
                {"type": "contains", "pattern": "API_KEY", "description": "API key"},
            ],
        }
        result = validate_file_requirement(req, tmp_path)
        assert all(c.status == CheckStatus.PASSED for c in result.checks), [
            (c.check_type, c.status, c.detail) for c in result.checks
        ]

    def test_java_function_exists(self, tmp_path: Path) -> None:
        java_file = tmp_path / "Service.java"
        java_file.write_text(dedent("""\
            public class UserService {
                public List<User> getUsers() {
                    return List.of();
                }
            }
        """))

        req = {
            "path": "Service.java",
            "purpose": "User service",
            "required": True,
            "checks": [
                {"type": "function_exists", "pattern": "getUsers", "description": "getter"},
                {"type": "class_exists", "pattern": "UserService", "description": "service class"},
            ],
        }
        result = validate_file_requirement(req, tmp_path)
        assert result.checks[0].status == CheckStatus.PASSED
        assert result.checks[1].status == CheckStatus.PASSED


# ---------------------------------------------------------------------------
# validate_function_requirement with non-Python files
# ---------------------------------------------------------------------------


class TestValidateFunctionRequirementMultiLang:
    @pytest.mark.asyncio
    async def test_ts_function_found(self, tmp_path: Path) -> None:
        ts_file = tmp_path / "handler.ts"
        ts_file.write_text(dedent("""\
            export async function handleWebhook(payload: any): Promise<void> {
                console.log(payload);
            }
        """))

        req = {
            "file": "handler.ts",
            "name": "handleWebhook",
            "required": True,
            "signature": "",
        }
        result = await validate_function_requirement(req, tmp_path)
        assert result.found is True
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_ts_function_not_found(self, tmp_path: Path) -> None:
        ts_file = tmp_path / "handler.ts"
        ts_file.write_text("export function otherFn() {}\n")

        req = {
            "file": "handler.ts",
            "name": "handleWebhook",
            "required": True,
            "signature": "",
        }
        result = await validate_function_requirement(req, tmp_path)
        assert result.found is False

    @pytest.mark.asyncio
    async def test_unsupported_file_gives_clear_message(self, tmp_path: Path) -> None:
        f = tmp_path / "script.sh"
        f.write_text("#!/bin/bash\nfunction deploy() { echo 'deploying'; }\n")

        req = {
            "file": "script.sh",
            "name": "deploy",
            "required": True,
            "signature": "",
        }
        result = await validate_function_requirement(req, tmp_path)
        assert result.found is False
        assert "not supported" in result.detail

    @pytest.mark.asyncio
    async def test_python_function_still_works(self, tmp_path: Path) -> None:
        py_file = tmp_path / "app.py"
        py_file.write_text(dedent("""\
            def process_data(items: list) -> dict:
                return {}
        """))

        req = {
            "file": "app.py",
            "name": "process_data",
            "required": True,
            "signature": "",
        }
        result = await validate_function_requirement(req, tmp_path)
        assert result.found is True
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_go_function_found(self, tmp_path: Path) -> None:
        go_file = tmp_path / "main.go"
        go_file.write_text(dedent("""\
            package main

            func ServeHTTP(w http.ResponseWriter, r *http.Request) {
                w.WriteHeader(200)
            }
        """))

        req = {
            "file": "main.go",
            "name": "ServeHTTP",
            "required": True,
            "signature": "",
        }
        result = await validate_function_requirement(req, tmp_path)
        assert result.found is True
        assert result.passed is True
