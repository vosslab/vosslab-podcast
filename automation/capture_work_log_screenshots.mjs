/**
 * Capture the locally rendered Vosslab Work Log landing page and newest post.
 *
 * This serves the sibling publisher's newest verified generated release on
 * localhost, blocks non-local browser requests, and copies two 1920x1200 PNGs
 * from an ignored repository output directory into this repository's documentation assets. It never
 * invokes a build, publishing, import, mirror refresh, or a model route.
 *
 * Run from this repository root:
 *   node automation/capture_work_log_screenshots.mjs
 */

import { createRequire } from 'node:module';
import { existsSync } from 'node:fs';
import { copyFile, mkdir, readdir, readFile, rm, stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { basename, dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptPath = fileURLToPath(import.meta.url);
const repositoryRoot = resolve(dirname(scriptPath), '..');
const publisherRoot = resolve(repositoryRoot, '..', 'vosslab-daily-blog');
const publicationsDirectory = join(publisherRoot, 'data', 'publications');
const screenshotsDirectory = join(repositoryRoot, 'docs', 'screenshots');
const captureDirectory = join(repositoryRoot, 'output_screenshot_capture');
const require = createRequire(join(publisherRoot, 'package.json'));
const { chromium } = require('playwright');

const viewport = { width: 1920, height: 1200 };
const landingCapture = {
	path: '/',
	fileName: 'work_log_landing_page.png',
	expectedHeading: 'Field notes from the workbench',
};


//============================================
function fail(message) {
	throw new Error(message);
}


//============================================
async function newestPostCapture() {
	const publicationNames = (await readdir(publicationsDirectory))
		.filter((name) => /^\d{4}-\d{2}-\d{2}\.json$/.test(name))
		.sort();
	if (publicationNames.length === 0) {
		fail(`No publisher publication records found: ${publicationsDirectory}`);
	}
	const publicationName = publicationNames.at(-1);
	const publication = JSON.parse(await readFile(join(publicationsDirectory, publicationName), 'utf8'));
	const reportDate = publication.report_date;
	if (reportDate !== publicationName.slice(0, -'.json'.length)) {
		fail(`Publication record date does not match its filename: ${publicationName}`);
	}
	const postPath = publication.post_path;
	if (typeof postPath !== 'string' || !postPath.startsWith('docs/blog/posts/')) {
		fail(`Publication record does not identify a blog source post: ${publicationName}`);
	}
	const postSource = await readFile(join(publisherRoot, postPath), 'utf8');
	const slug = postSource.match(/^slug:\s*(.+)$/m)?.[1]?.trim();
	const expectedHeading = postSource.match(/^#\s+(.+)$/m)?.[1]?.trim();
	if (!slug || !expectedHeading) {
		fail(`Publication source post has no slug or heading: ${postPath}`);
	}
	return {
		site: join(publisherRoot, 'generated', 'releases', reportDate),
		capture: {
			path: `/blog/${reportDate.replaceAll('-', '/')}/${slug}/`,
			fileName: 'latest_work_log_post.png',
			expectedHeading,
		},
	};
}


//============================================
function capturesFor(postCapture) {
	return [
		landingCapture,
		postCapture,
	];
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
async function capturePages(baseUrl, tempDirectory, captures) {
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
					const header = document.querySelector('.md-header');
					const headerInner = document.querySelector('.md-header__inner');
					const headerTitle = document.querySelector('[data-md-component="header-title"]');
					if (!(header instanceof HTMLElement) || !(headerInner instanceof HTMLElement)) {
						throw new Error('The rendered page has no complete site header.');
					}
					header.removeAttribute('hidden');
					header.style.setProperty('display', 'block', 'important');
					header.style.setProperty('position', 'fixed', 'important');
					header.style.setProperty('top', '0', 'important');
					header.style.setProperty('left', '0', 'important');
					header.style.setProperty('right', '0', 'important');
					header.style.setProperty('z-index', '100', 'important');
					header.style.setProperty('transform', 'translateY(0)', 'important');
					header.style.setProperty('transition', 'none', 'important');
					header.style.setProperty('visibility', 'visible', 'important');
					header.style.setProperty('opacity', '1', 'important');
					headerInner.style.setProperty('transform', 'none', 'important');
					headerInner.style.setProperty('transition', 'none', 'important');
					if (headerTitle instanceof HTMLElement) {
						headerTitle.classList.remove('md-header__title--active');
						const topics = headerTitle.querySelectorAll('.md-header__topic');
						topics.forEach((topic, index) => {
							if (!(topic instanceof HTMLElement)) {
								return;
							}
							topic.style.setProperty('opacity', index === 0 ? '1' : '0', 'important');
							topic.style.setProperty('transform', 'none', 'important');
							topic.style.setProperty('z-index', index === 0 ? '0' : '-1', 'important');
						});
					}
				});
				await page.waitForFunction(() => {
					const header = document.querySelector('.md-header');
					const title = header?.querySelector('[data-md-component="header-title"]');
					const siteTitle = header?.querySelector('.md-header__topic:first-child');
					const logo = header?.querySelector('.md-logo img');
					const headerBounds = header?.getBoundingClientRect();
					const titleBounds = title?.getBoundingClientRect();
					const siteTitleBounds = siteTitle?.getBoundingClientRect();
					const logoBounds = logo?.getBoundingClientRect();
					const siteTitleStyle = siteTitle && getComputedStyle(siteTitle);
					const logoStyle = logo && getComputedStyle(logo);
					return window.scrollX === 0 && window.scrollY === 0
						&& headerBounds && headerBounds.top === 0 && headerBounds.height >= 48
						&& headerBounds.bottom <= window.innerHeight
						&& titleBounds && titleBounds.top >= 0 && titleBounds.bottom <= headerBounds.bottom
						&& siteTitleBounds && siteTitleBounds.top >= 0 && siteTitleBounds.bottom <= headerBounds.bottom
						&& logoBounds && logoBounds.top >= 0 && logoBounds.bottom <= headerBounds.bottom
						&& siteTitle?.textContent?.trim() === 'Vosslab Work Log'
						&& siteTitleStyle?.opacity === '1' && siteTitleStyle.visibility === 'visible'
						&& logoStyle?.opacity !== '0' && logoStyle?.visibility === 'visible';
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
	const { site: publisherSite, capture: postCapture } = await newestPostCapture();
	const captures = capturesFor(postCapture);
	if (!existsSync(publisherSite)) {
		fail(`Verified local publisher output is missing: ${publisherSite}`);
	}
	await rm(captureDirectory, { recursive: true, force: true });
	await mkdir(captureDirectory, { recursive: true });
	process.env.TMPDIR = captureDirectory;
	try {
		const { server, baseUrl } = await startStaticServer(publisherSite);
		try {
			await capturePages(baseUrl, captureDirectory, captures);
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
		console.log(`Captured ${captures.length} screenshots from ${publisherSite}`);
	} finally {
		await rm(captureDirectory, { recursive: true, force: true });
	}
}

await main();
