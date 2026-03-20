"""Tests for regex-based multi-language name extraction."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from skene.validators.regex_parser import ExtractedNames, extract_names, supported_suffix


# ---------------------------------------------------------------------------
# supported_suffix
# ---------------------------------------------------------------------------


class TestSupportedSuffix:
    @pytest.mark.parametrize(
        "suffix",
        [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".java", ".go", ".rb", ".rs", ".php", ".cs", ".kt", ".swift", ".dart"],
    )
    def test_known_extensions(self, suffix: str) -> None:
        assert supported_suffix(suffix) is True

    @pytest.mark.parametrize("suffix", [".py", ".txt", ".md", ".yaml", ".toml", ""])
    def test_unsupported_extensions(self, suffix: str) -> None:
        assert supported_suffix(suffix) is False


# ---------------------------------------------------------------------------
# TypeScript / JavaScript extraction
# ---------------------------------------------------------------------------


class TestTypeScriptExtraction:
    def test_function_declaration(self, tmp_path: Path) -> None:
        f = tmp_path / "app.ts"
        f.write_text(dedent("""\
            export function integrateWithWordPress(config: WPConfig): void {
                console.log('integrating');
            }
        """))
        result = extract_names(f)
        assert result is not None
        assert "integrateWithWordPress" in result.functions

    def test_async_function(self, tmp_path: Path) -> None:
        f = tmp_path / "api.ts"
        f.write_text(dedent("""\
            export async function fetchData(url: string): Promise<Response> {
                return fetch(url);
            }
        """))
        result = extract_names(f)
        assert result is not None
        assert "fetchData" in result.functions

    def test_arrow_function_const(self, tmp_path: Path) -> None:
        f = tmp_path / "utils.ts"
        f.write_text(dedent("""\
            export const handleClick = (event: MouseEvent) => {
                event.preventDefault();
            };
            const processData = async (data: any) => {
                return data;
            };
        """))
        result = extract_names(f)
        assert result is not None
        assert "handleClick" in result.functions
        assert "processData" in result.functions

    def test_class_and_interface(self, tmp_path: Path) -> None:
        f = tmp_path / "models.ts"
        f.write_text(dedent("""\
            export class UserService {
                constructor() {}
            }
            export interface IAuthProvider {
                login(): Promise<void>;
            }
            type Config = {
                apiKey: string;
            };
            enum Status {
                Active,
                Inactive,
            }
        """))
        result = extract_names(f)
        assert result is not None
        assert "UserService" in result.classes
        assert "IAuthProvider" in result.classes
        assert "Config" in result.classes
        assert "Status" in result.classes

    def test_imports(self, tmp_path: Path) -> None:
        f = tmp_path / "index.ts"
        f.write_text(dedent("""\
            import { useState, useEffect } from 'react';
            import axios from 'axios';
            import './styles.css';
        """))
        result = extract_names(f)
        assert result is not None
        assert "react" in result.imports
        assert "axios" in result.imports
        assert "./styles.css" in result.imports

    def test_require_import(self, tmp_path: Path) -> None:
        f = tmp_path / "server.js"
        f.write_text(dedent("""\
            const express = require('express');
            const path = require('path');
        """))
        result = extract_names(f)
        assert result is not None
        assert "express" in result.imports
        assert "path" in result.imports

    def test_ignores_commented_functions(self, tmp_path: Path) -> None:
        f = tmp_path / "commented.ts"
        f.write_text(dedent("""\
            // function oldFunction() {}
            /* function removedFunction() {} */
            export function activeFunction(): void {}
        """))
        result = extract_names(f)
        assert result is not None
        assert "activeFunction" in result.functions
        assert "oldFunction" not in result.functions
        assert "removedFunction" not in result.functions

    def test_class_method(self, tmp_path: Path) -> None:
        f = tmp_path / "service.ts"
        f.write_text(dedent("""\
            class ApiService {
                public async getData(id: string): Promise<Data> {
                    return this.fetch(id);
                }
                private processResponse(res: Response): Data {
                    return res.json();
                }
            }
        """))
        result = extract_names(f)
        assert result is not None
        assert "getData" in result.functions
        assert "processResponse" in result.functions


# ---------------------------------------------------------------------------
# Java extraction
# ---------------------------------------------------------------------------


class TestJavaExtraction:
    def test_methods_and_class(self, tmp_path: Path) -> None:
        f = tmp_path / "App.java"
        f.write_text(dedent("""\
            package com.example;

            import java.util.List;
            import com.google.common.collect.ImmutableList;

            public class UserController {
                public List<User> getUsers() {
                    return ImmutableList.of();
                }
                private void processUser(User user) {}
            }
        """))
        result = extract_names(f)
        assert result is not None
        assert "UserController" in result.classes
        assert "getUsers" in result.functions
        assert "processUser" in result.functions
        assert "java.util.List" in result.imports
        assert "com.google.common.collect.ImmutableList" in result.imports


# ---------------------------------------------------------------------------
# Go extraction
# ---------------------------------------------------------------------------


class TestGoExtraction:
    def test_func_and_struct(self, tmp_path: Path) -> None:
        f = tmp_path / "main.go"
        f.write_text(dedent("""\
            package main

            import "fmt"

            type Server struct {
                Port int
            }

            type Handler interface {
                ServeHTTP()
            }

            func (s *Server) Start() error {
                return nil
            }

            func NewServer(port int) *Server {
                return &Server{Port: port}
            }
        """))
        result = extract_names(f)
        assert result is not None
        assert "Server" in result.classes
        assert "Handler" in result.classes
        assert "Start" in result.functions
        assert "NewServer" in result.functions
        assert "fmt" in result.imports


# ---------------------------------------------------------------------------
# Ruby extraction
# ---------------------------------------------------------------------------


class TestRubyExtraction:
    def test_class_and_methods(self, tmp_path: Path) -> None:
        f = tmp_path / "user.rb"
        f.write_text(dedent("""\
            require 'json'
            require_relative 'base'

            module Auth
              class User
                def initialize(name)
                  @name = name
                end

                def self.find(id)
                  # ...
                end

                def valid?
                  @name.present?
                end
              end
            end
        """))
        result = extract_names(f)
        assert result is not None
        assert "Auth" in result.classes
        assert "User" in result.classes
        assert "initialize" in result.functions
        assert "find" in result.functions
        assert "valid?" in result.functions
        assert "json" in result.imports
        assert "base" in result.imports


# ---------------------------------------------------------------------------
# Rust extraction
# ---------------------------------------------------------------------------


class TestRustExtraction:
    def test_fn_struct_trait(self, tmp_path: Path) -> None:
        f = tmp_path / "lib.rs"
        f.write_text(dedent("""\
            use std::collections::HashMap;

            pub struct Config {
                pub port: u16,
            }

            pub trait Handler {
                fn handle(&self);
            }

            pub async fn serve(config: Config) -> Result<(), Error> {
                Ok(())
            }

            fn internal_helper() {}
        """))
        result = extract_names(f)
        assert result is not None
        assert "Config" in result.classes
        assert "Handler" in result.classes
        assert "serve" in result.functions
        assert "internal_helper" in result.functions
        assert "std::collections::HashMap" in result.imports


# ---------------------------------------------------------------------------
# PHP extraction
# ---------------------------------------------------------------------------


class TestPHPExtraction:
    def test_class_and_function(self, tmp_path: Path) -> None:
        f = tmp_path / "Controller.php"
        f.write_text(dedent("""\
            <?php
            use App\\Models\\User;

            class UserController {
                public function index() {
                    return User::all();
                }
                private function validate($data) {}
            }
        """))
        result = extract_names(f)
        assert result is not None
        assert "UserController" in result.classes
        assert "index" in result.functions
        assert "validate" in result.functions
        assert "App\\Models\\User" in result.imports


# ---------------------------------------------------------------------------
# C# extraction
# ---------------------------------------------------------------------------


class TestCSharpExtraction:
    def test_class_and_methods(self, tmp_path: Path) -> None:
        f = tmp_path / "Service.cs"
        f.write_text(dedent("""\
            using System;
            using System.Collections.Generic;

            namespace MyApp {
                public class UserService {
                    public async Task<List<User>> GetUsersAsync() {
                        return new List<User>();
                    }
                    private void ProcessData(string data) {}
                }

                public interface IUserRepository {
                    Task<User> FindById(int id);
                }
            }
        """))
        result = extract_names(f)
        assert result is not None
        assert "UserService" in result.classes
        assert "IUserRepository" in result.classes
        assert "GetUsersAsync" in result.functions
        assert "ProcessData" in result.functions
        assert "System" in result.imports
        assert "System.Collections.Generic" in result.imports


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_unsupported_extension_returns_none(self, tmp_path: Path) -> None:
        f = tmp_path / "data.yaml"
        f.write_text("key: value\n")
        assert extract_names(f) is None

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        f = tmp_path / "nonexistent.ts"
        assert extract_names(f) is None

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.ts"
        f.write_text("")
        result = extract_names(f)
        assert result is not None
        assert result.functions == []
        assert result.classes == []
        assert result.imports == []

    def test_jsx_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "Component.jsx"
        f.write_text(dedent("""\
            import React from 'react';
            export default function MyComponent() {
                return <div>Hello</div>;
            }
        """))
        result = extract_names(f)
        assert result is not None
        assert "MyComponent" in result.functions
        assert "react" in result.imports
