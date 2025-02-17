import type {NextConfig} from "next";

const nextConfig: NextConfig = {
    /* config options here */
    output: "export",
    distDir: "build",
};

// Only apply rewrites in development mode
if (process.env.NODE_ENV === "development") {
    nextConfig.rewrites = async function () {
        // Dev server API proxy
        return [
            {
                source: '/api/:path*', // Match requests starting with "/api" and capture the rest
                destination: 'http://localhost:8000/api/:path*', // Proxy to localhost:8000/api
            },
        ];
    }

    // Suppress a warning during dev server running
    nextConfig.output = undefined;
}

export default nextConfig;
