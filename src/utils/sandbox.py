"""Vercel Sandbox wrapper for safe code execution."""

import asyncio
from typing import Any
from vercel.sandbox import AsyncSandbox as Sandbox


class CodeExecutionResult:
    """Result from code execution in sandbox."""

    def __init__(
        self,
        success: bool,
        output: str,
        error: str | None = None,
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
    ):
        self.success = success
        self.output = output
        self.error = error
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self) -> str:
        if self.success:
            return f"Success: {self.output}"
        return f"Error (exit code {self.exit_code}): {self.error}"


class SandboxManager:
    """Manager for Vercel Sandbox instances."""

    def __init__(
        self,
        runtime: str = "python3.13",
        timeout: int = 300_000,  # 5 minutes default
        vcpus: int = 2,
    ):
        """Initialize sandbox manager.

        Args:
            runtime: Runtime environment (python3.13 or node22)
            timeout: Timeout in milliseconds
            vcpus: Number of vCPUs to allocate
        """
        self.runtime = runtime
        self.timeout = timeout
        self.vcpus = vcpus
        self.sandbox: Sandbox | None = None

    async def create_sandbox(self) -> Sandbox:
        """Create a new sandbox instance."""
        self.sandbox = await Sandbox.create(
            resources={"vcpus": self.vcpus},
            timeout=self.timeout,
            runtime=self.runtime,
        )
        return self.sandbox

    async def execute_python(
        self,
        code: str,
        timeout_seconds: int = 60,
    ) -> CodeExecutionResult:
        """Execute Python code in the sandbox.

        Args:
            code: Python code to execute
            timeout_seconds: Execution timeout in seconds

        Returns:
            CodeExecutionResult with execution details
        """
        if not self.sandbox:
            await self.create_sandbox()

        try:
            # Write code to a file
            write_cmd = await self.sandbox.run_command_detached(
                "bash",
                ["-c", f"cat > /tmp/exec.py << 'EOFMARKER'\n{code}\nEOFMARKER"]
            )
            await write_cmd.wait()

            # Execute the code
            exec_cmd = await self.sandbox.run_command_detached(
                "python3",
                ["/tmp/exec.py"]
            )

            # Collect output with timeout
            stdout_lines = []
            stderr_lines = []

            async def collect_logs():
                async for line in exec_cmd.logs():
                    if line.stream == "stdout":
                        stdout_lines.append(line.data)
                    else:
                        stderr_lines.append(line.data)

            try:
                await asyncio.wait_for(collect_logs(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                await exec_cmd.kill()
                return CodeExecutionResult(
                    success=False,
                    output="",
                    error=f"Execution timed out after {timeout_seconds} seconds",
                    exit_code=-1,
                    stdout="".join(stdout_lines),
                    stderr="".join(stderr_lines)
                )

            # Wait for completion
            result = await exec_cmd.wait()

            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)

            if result.exit_code == 0:
                return CodeExecutionResult(
                    success=True,
                    output=stdout,
                    exit_code=0,
                    stdout=stdout,
                    stderr=stderr
                )
            else:
                return CodeExecutionResult(
                    success=False,
                    output=stdout,
                    error=stderr or "Execution failed",
                    exit_code=result.exit_code,
                    stdout=stdout,
                    stderr=stderr
                )

        except Exception as e:
            return CodeExecutionResult(
                success=False,
                output="",
                error=f"Sandbox error: {str(e)}",
                exit_code=-1
            )

    async def install_package(self, package: str) -> bool:
        """Install a Python package in the sandbox.

        Args:
            package: Package name to install (e.g., "numpy" or "requests==2.28.0")

        Returns:
            True if installation successful
        """
        if not self.sandbox:
            await self.create_sandbox()

        try:
            install_cmd = await self.sandbox.run_command_detached(
                "pip",
                ["install", package]
            )

            # Collect output
            async for _ in install_cmd.logs():
                pass  # Just consume the logs

            result = await install_cmd.wait()
            return result.exit_code == 0

        except Exception:
            return False

    async def execute_with_packages(
        self,
        code: str,
        packages: list[str],
        timeout_seconds: int = 60,
    ) -> CodeExecutionResult:
        """Execute Python code after installing required packages.

        Args:
            code: Python code to execute
            packages: List of packages to install
            timeout_seconds: Execution timeout in seconds

        Returns:
            CodeExecutionResult
        """
        # Install packages first
        for package in packages:
            success = await self.install_package(package)
            if not success:
                return CodeExecutionResult(
                    success=False,
                    output="",
                    error=f"Failed to install package: {package}",
                    exit_code=-1
                )

        # Execute code
        return await self.execute_python(code, timeout_seconds)

    async def cleanup(self) -> None:
        """Stop and cleanup the sandbox."""
        if self.sandbox:
            try:
                await self.sandbox.stop()
            except Exception:
                pass  # Ignore cleanup errors
            finally:
                self.sandbox = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.create_sandbox()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()


async def execute_python_code(
    code: str,
    packages: list[str] | None = None,
    timeout_seconds: int = 60,
) -> CodeExecutionResult:
    """Quick helper to execute Python code in a temporary sandbox.

    Args:
        code: Python code to execute
        packages: Optional list of packages to install
        timeout_seconds: Execution timeout

    Returns:
        CodeExecutionResult
    """
    async with SandboxManager() as manager:
        if packages:
            return await manager.execute_with_packages(code, packages, timeout_seconds)
        else:
            return await manager.execute_python(code, timeout_seconds)
