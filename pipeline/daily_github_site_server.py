#!/usr/bin/env python3
import argparse
import functools
import http.server
import os

from podlib import daily_github_site
from podlib import pipeline_settings


class StaticRequestHandler(http.server.SimpleHTTPRequestHandler):
	"""
	Serve generated static files while retaining query-free local access records.
	"""

	access_log_path = ""

	#============================================
	def log_request(self, code="-", size="-") -> None:
		"""
		Write one local request record without retaining a query string.
		"""
		if not self.access_log_path:
			return
		request_path = self.path.split("?", 1)[0]
		line = f"{self.log_date_time_string()} {self.command} {request_path} {code} {size}\n"
		with open(self.access_log_path, "a", encoding="utf-8") as handle:
			handle.write(line)


#============================================
def parse_args() -> argparse.Namespace:
	"""
	Parse safe private-LAN static server arguments.
	"""
	parser = argparse.ArgumentParser(
		description="Serve an already-built daily GitHub static archive on one private LAN address."
	)
	parser.add_argument(
		"-s",
		"--settings",
		dest="settings_path",
		default="settings.yaml",
		help="YAML settings path containing daily_site.bind_address and daily_site.port.",
	)
	parser.add_argument(
		"-o",
		"--output-root",
		dest="output_root",
		default="out",
		help="Output root used for the default user-scoped static archive path.",
	)
	parser.add_argument(
		"--site-root",
		dest="site_root",
		default="",
		help="Explicit static-site directory; default is <root>/<user>/daily_site/.",
	)
	parser.add_argument(
		"-b",
		"--bind-address",
		dest="bind_address",
		default="",
		help="Explicit private LAN IPv4 override; it is validated before listen.",
	)
	parser.add_argument(
		"-p",
		"--port",
		dest="port",
		type=int,
		default=None,
		help="Non-privileged TCP port override; defaults to daily_site.port.",
	)
	parser.add_argument(
		"--access-log",
		dest="access_log_path",
		default="out/logs/daily_github_site/access.log",
		help="Local access log path; default remains under out/logs/.",
	)
	args = parser.parse_args()
	return args


#============================================
def resolve_server_configuration(args: argparse.Namespace) -> tuple[str, int, str, str]:
	"""
	Resolve configured private bind values and the user-scoped static archive root.
	"""
	settings, _ = pipeline_settings.load_settings(args.settings_path)
	username = pipeline_settings.get_github_username(settings)
	configured_address = pipeline_settings.get_setting_str(
		settings,
		["daily_site", "bind_address"],
		"",
	)
	configured_port = pipeline_settings.get_setting_int(settings, ["daily_site", "port"], 8765)
	bind_address = args.bind_address.strip() or configured_address
	port = args.port if args.port is not None else configured_port
	address, validated_port = daily_github_site.validate_private_server_configuration(bind_address, port)
	_, site_root = daily_github_site.resolve_approved_site_root(
		args.output_root,
		username,
		args.site_root,
	)
	access_log_path = os.path.abspath(args.access_log_path)
	return address, validated_port, site_root, access_log_path


#============================================
def create_site_server(address: str, port: int, site_root: str, access_log_path: str) -> http.server.ThreadingHTTPServer:
	"""
	Create one validated local static server; port zero is reserved for owned E2E sockets only.
	"""
	if port == 0:
		daily_github_site.validate_private_bind_address(address)
	else:
		daily_github_site.validate_private_server_configuration(address, port)
	if not daily_github_site.is_directory_nonsymlink(site_root):
		raise RuntimeError(f"Static archive must be a regular directory: {site_root}")
	index_path = os.path.join(site_root, "index.html")
	if not daily_github_site.is_regular_nonsymlink(index_path):
		raise RuntimeError(f"Static archive is missing a regular index.html: {site_root}")
	os.makedirs(os.path.dirname(access_log_path), exist_ok=True)
	StaticRequestHandler.access_log_path = access_log_path
	handler = functools.partial(StaticRequestHandler, directory=site_root)
	server = http.server.ThreadingHTTPServer((address, port), handler)
	return server


#============================================
def serve_site(address: str, port: int, site_root: str, access_log_path: str) -> None:
	"""
	Listen only after validation has accepted a configured private LAN endpoint.
	"""
	server = create_site_server(address, port, site_root, access_log_path)
	print(f"Daily GitHub static archive listening at http://{address}:{port}/", flush=True)
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		print("Daily GitHub static archive stopped.", flush=True)
	finally:
		server.server_close()


#============================================
def main() -> None:
	"""
	Resolve and serve the existing private static archive.
	"""
	args = parse_args()
	address, port, site_root, access_log_path = resolve_server_configuration(args)
	serve_site(address, port, site_root, access_log_path)


if __name__ == "__main__":
	main()
