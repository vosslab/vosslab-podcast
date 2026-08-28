/**
 * Capture the locally rendered Vosslab Work Log landing page and Aug. 26 post.
 *
 * This serves the sibling publisher's verified generated/check output on
 * localhost, blocks non-local browser requests, and copies two 1280x800 PNGs
 * from an ignored repository output directory into this repository's documentation assets. It never
 * invokes a build, publishing, import, mirror refresh, or a model route.
 *
 * Run from this repository root:
 *   node automation/capture_work_log_screenshots.mjs
 */

import { createRequire } from 'node:module';
import { existsSync } from 'node:fs';
import { copyFile, mkdir, readFile, rm, stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { basename, dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptPath = fileURLToPath(import.meta.url);
const repositoryRoot = resolve(dirname(scriptPath), '..');
const publisherRoot = resolve(repositoryRoot, '..', 'vosslab-daily-blog');
const publisherSite = join(publisherRoot, 'generated', 'check');
const screenshotsDirectory = join(repositoryRoot, 'docs', 'screenshots');
const captureDirectory = join(repositoryRoot, 'output_screenshot_capture');
const require = createRequire(join(publisherRoot, 'package.json'));
const { chromium } = require('playwright');

const viewport = { width: 1280, height: 800 };
const captures = [
	{
		path: '/',
		fileName: 'work_log_landing_page.png',
		expectedHeading: 'Field notes from the workbench',
	},
	{
		path: '/blog/2026/08/26/making-the-interface-tell-the-truth/',
		fileName: 'making_the_interface_tell_the_truth.png',
		expectedHeading: 'Making the Interface Tell the Truth',
	},
];


//============================================
function fail(message) {
	throw new Error(message);
}


//============================================
function contentType(fileName) {
	const contentTypes = {
		'.css': 'text/css; charset=utf-8',
		'.html': 'text/html; charset=utf-8',
		'.js': 'text/javascript; charset=utf-8',
		'.json': 'application/json; charset=utf-8',
		'.png': 'image/png',
		'.svg': 'image/svg+xml',
		'.webmanifest': 'application/manifest+json',
		'.woff2': 'font/woff2',
	};
	return contentTypes[extname(fileName)] || 'application/octet-stream';
}


//============================================
async function startStaticServer(siteDirectory) {
	const safeRoot = resolve(siteDirectory);
	const server = createServer(async (request, response) => {
		try {
			const requestPath = new URL(request.url, 'http://127.0.0.1').pathname;
			const decodedPath = decodeURIComponent(requestPath);
			const relativePath = decodedPath === '/' ? 'index.html' : decodedPath.replace(/^\/+/, '');
			let requestedFile = resolve(siteDirectory, relativePath);
			if (requestedFile !== safeRoot && !requestedFile.startsWith(`${safeRoot}/`)) {
				response.writeHead(403);
				response.end('Forbidden');
				return;
			}
			try {
				const requestedStat = await stat(requestedFile);
				if (requestedStat.isDirectory()) {
					requestedFile = join(requestedFile, 'index.html');
				}
			} catch {
				if (!basename(requestedFile).includes('.')) {
					requestedFile = join(requestedFile, 'index.html');
				}
			}
			const contents = await readFile(requestedFile);
			response.writeHead(200, { 'content-type': contentType(requestedFile) });
			response.end(contents);
		} catch {
			response.writeHead(404);
			response.end('Not found');
		}
	});
	await new Promise((resolveServer) => server.listen(0, '127.0.0.1', resolveServer));
	const address = server.address();
	if (!address || typeof address === 'string') {
		fail('Could not resolve local static server address.');
	}
	return { server, baseUrl: `http://127.0.0.1:${address.port}` };
}


//============================================
async function capturePages(baseUrl, tempDirectory) {
	const browser = await chromium.launch({
		env: { ...process.env, TMPDIR: tempDirectory },
	});
	try {
		for (const capture of captures) {
			const page = await browser.newPage({ viewport });
			try {
				await page.route('**/*', (route) => {
					const requestUrl = route.request().url();
					if (requestUrl.startsWith(baseUrl)) {
						return route.continue();
					}
					return route.abort();
				});
				const response = await page.goto(`${baseUrl}${capture.path}`, {
					waitUntil: 'networkidle',
				});
				if (!response || !response.ok()) {
					fail(`Capture page failed HTTP validation: ${capture.path}`);
				}
				await page.evaluate(() => document.fonts.ready);
				const heading = page.locator('h1').first();
				await heading.waitFor({ state: 'visible' });
				const headingText = (await heading.textContent()) || '';
				if (!headingText.includes(capture.expectedHeading)) {
					fail(`Capture page identity did not match: ${capture.path}`);
				}
				await page.evaluate(() => {
					window.scrollTo(0, 0);
					// Material can retain its auto-hide state after navigation even at the
					// document origin. Pin the header in its fully visible top-of-page
					// state so a delayed scroll listener cannot translate it during capture.
					const header = document.querySelector('.md-header');
					header?.removeAttribute('hidden');
					if (header instanceof HTMLElement) {
						header.style.transform = 'translateY(0)';
						header.style.transition = 'none';
					}
				});
				await page.waitForFunction(() => {
					const header = document.querySelector('.md-header');
					const bounds = header?.getBoundingClientRect();
					return window.scrollX === 0 && window.scrollY === 0
						&& bounds && bounds.top === 0 && bounds.height >= 48
						&& bounds.bottom <= window.innerHeight;
				});
				await page.screenshot({ path: join(tempDirectory, capture.fileName) });
			} finally {
				await page.close();
			}
		}
	} finally {
		await browser.close();
	}
}


//============================================
async function main() {
	if (!existsSync(publisherSite)) {
		fail(`Verified local publisher output is missing: ${publisherSite}`);
	}
	await rm(captureDirectory, { recursive: true, force: true });
	await mkdir(captureDirectory, { recursive: true });
	process.env.TMPDIR = captureDirectory;
	try {
		const { server, baseUrl } = await startStaticServer(publisherSite);
		try {
			await capturePages(baseUrl, captureDirectory);
		} finally {
			await new Promise((resolveClose) => server.close(resolveClose));
		}
		await mkdir(screenshotsDirectory, { recursive: true });
		for (const capture of captures) {
			const sourcePath = join(captureDirectory, capture.fileName);
			const sourceStat = await stat(sourcePath);
			if (sourceStat.size > 1_000_000) {
				fail(`${capture.fileName} exceeds the 1 MB documentation image budget.`);
			}
			await copyFile(sourcePath, join(screenshotsDirectory, capture.fileName));
		}
		console.log(`Captured ${captures.length} screenshots in ${screenshotsDirectory}`);
	} finally {
		await rm(captureDirectory, { recursive: true, force: true });
	}
}

await main();
