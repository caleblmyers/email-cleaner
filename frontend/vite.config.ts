import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		proxy: {
			'/auth': 'http://localhost:8000',
			'/emails': {
				target: 'http://localhost:8000',
				// Required for SSE — don't buffer the response
				configure: (proxy) => {
					proxy.on('proxyReq', (proxyReq, req) => {
						if (req.url?.includes('/stream')) {
							proxyReq.setHeader('Accept', 'text/event-stream');
						}
					});
				}
			},
			'/categories': 'http://localhost:8000',
			'/labels': 'http://localhost:8000'
		}
	}
});
