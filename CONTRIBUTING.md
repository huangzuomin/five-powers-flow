# Contributing to Five-Powers-Flow (FPF)

Thank you for your interest in contributing to the **Five-Powers-Flow** project! We believe that bringing rigorous constitutional checks and balances to autonomous multi-agent engineering is essential for safe, high-assurance software development.

## 🤝 Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## 💡 How Can You Contribute?

You can contribute to Five-Powers-Flow in several ways:
1. **RFCs & Specification Enhancements**: Propose improvements to `docs/SPECIFICATION.md` via GitHub Discussions or PRs.
2. **Channel Adapters**: Build new transport adapters for agents (e.g., Claude Desktop, Cursor, OpenAI Swarm, LangGraph, OpenHands).
3. **Quality Gates & Tooling**: Enhance zero-mock verification tooling, mutation testing helpers, and evidence pack generators.
4. **Templates & Best Practices**: Share generic `LESSONS.md` patterns and discipline templates.

## 🛠️ Development & Submission Process

1. **Fork the Repository**: Create a fork of `huangzuomin/five-powers-flow`.
2. **Create a Topic Branch**: Use branch prefixes like `feat/`, `fix/`, or `docs/`.
3. **Commit Cleanly**: Follow conventional commit formats (`feat: add xxx adapter`, `fix: enforce 40-digit sha in schema`).
4. **Validate Schemas**: Ensure all JSON Schemas and markdown examples are syntactically valid.
5. **Open a Pull Request**: Provide a clear description of changes referencing any related issues.

## 📜 Pull Request Guidelines

- All documentation and specs must preserve the cardinal rule:
  $$\text{DEV Delivery} \neq \text{QA Pass} \neq \text{Merge Approval} \neq \text{Deploy Approval}$$
- Do not introduce single-agent bypasses that compromise auditability or physical isolation.
