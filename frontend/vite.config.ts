import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		proxy: {
			'/auth': 'http://localhost:8000',
			'/emails': 'http://localhost:8000',
			'/categories': 'http://localhost:8000',
			'/labels': 'http://localhost:8000'
		}
	}
});
