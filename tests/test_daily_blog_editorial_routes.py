"""Focused route-boundary checks for daily-blog editorial processes."""

# Standard Library
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.config


#============================================
@pytest.mark.parametrize(
	"provider_arguments",
	(
		"",
		"--provider",
		"--provider, other-provider",
		"--provider, openai-codex, --provider, openai-codex",
		"--provider=openai-codex, --provider=openai-codex",
	),
)
def test_hermes_route_requires_one_openai_codex_provider(
	tmp_path: pathlib.Path,
	provider_arguments: str,
) -> None:
	"""Every Hermes role enters the configured OpenAI Codex account pool explicitly."""
	settings_path = tmp_path / "settings.yaml"
	provider_fragment = f", {provider_arguments}" if provider_arguments else ""
	settings_path.write_text(
		"github:\n"
		"  username: vosslab\n"
		"  identity_login: vosslab\n"
		"daily_blog:\n"
		"  routes:\n"
		"    authors:\n"
		"      - name: one\n"
		+ f"        command: [hermes, chat{provider_fragment}, --ignore-rules, --query-file, -]\n"
		"      - name: two\n"
		"        command: [hermes, chat, --provider, openai-codex, --ignore-rules, --query-file, -]\n"
		"    referee:\n"
		"      name: judge\n"
		"      command: [hermes, chat, --provider, openai-codex, --ignore-rules, --query-file, -]\n",
		encoding="utf-8",
	)

	with pytest.raises(RuntimeError, match="sealed Hermes editorial route"):
		daily_blog.config.load_config(str(settings_path))


#============================================
@pytest.mark.parametrize(
	"model_arguments",
	("--model, preferred", "--model=preferred", "-m, preferred", "model=preferred"),
)
def test_hermes_route_leaves_model_selection_to_hermes(
	tmp_path: pathlib.Path,
	model_arguments: str,
) -> None:
	"""The project selects only the provider and never pins a model."""
	settings_path = tmp_path / "settings.yaml"
	settings_path.write_text(
		"github:\n"
		"  username: vosslab\n"
		"  identity_login: vosslab\n"
		"daily_blog:\n"
		"  routes:\n"
		"    authors:\n"
		"      - name: one\n"
		+ f"        command: [hermes, chat, --provider, openai-codex, {model_arguments}, --ignore-rules, --query-file, -]\n"
		"      - name: two\n"
		"        command: [hermes, chat, --provider, openai-codex, --ignore-rules, --query-file, -]\n"
		"    referee:\n"
		"      name: judge\n"
		"      command: [hermes, chat, --provider, openai-codex, --ignore-rules, --query-file, -]\n",
		encoding="utf-8",
	)

	with pytest.raises(RuntimeError, match="model selection"):
		daily_blog.config.load_config(str(settings_path))


#============================================
@pytest.mark.parametrize(
	"modifier",
	(
		("--in", "/workspace"),
		("--quiet",),
		("--toolsets", "editorial"),
		("--profile", "isolated"),
		("--image", "reference.png"),
		("--query", "inline"),
		("--resume", "latest"),
		("--skills", "daily-blog"),
		("--continue",),
	),
)
def test_hermes_route_rejects_every_extra_modifier(modifier: tuple[str, ...]) -> None:
	"""The project has no route-level configuration beyond the sealed transport."""
	command = (*daily_blog.config.HERMES_EDITORIAL_ROUTE, *modifier)

	with pytest.raises(RuntimeError, match="sealed Hermes editorial route"):
		daily_blog.config._validate_role_command(command, "test")
