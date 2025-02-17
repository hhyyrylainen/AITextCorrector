import type {Metadata} from "next";
import Image from "next/image";
import Link from "next/link";
import {Geist, Geist_Mono} from "next/font/google";
import "./globals.css";
import React from "react";

const geistSans = Geist({
    variable: "--font-geist-sans",
    subsets: ["latin"],
});

const geistMono = Geist_Mono({
    variable: "--font-geist-mono",
    subsets: ["latin"],
});

export const metadata: Metadata = {
    title: "AI Text Corrector",
    description: "AI test proofreading tool",
};

export default function RootLayout({
                                       children,
                                   }: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en">
        <body
            className={`${geistSans.variable} ${geistMono.variable} antialiased`}
        >
        {/* Page Layout */}
        <div className="flex flex-col min-h-screen">
            {/* Header */}
            <header className="bg-gray-800 text-white py-4 text-center">
                <h1 className="text-lg font-bold">AI Text Corrector</h1>
            </header>

            {/* Main Content */}
            <main className="py-10 flex-grow flex flex-col items-center">
                <div className="w-full flex-grow flex flex-col items-center px-4">
                    {children}
                </div>
            </main>

            {/* Footer */}
            <footer className="bg-gray-800 text-white py-4 gap-6 text-center flex justify-center">
                <Link
                    className="flex items-center gap-2 hover:underline hover:underline-offset-4"
                    href="/create"
                >
                    <Image
                        aria-hidden
                        src="/file.svg"
                        alt="File icon"
                        width={16}
                        height={16}
                    />
                    New
                </Link>
                <Link
                    className="flex items-center gap-2 hover:underline hover:underline-offset-4"
                    href="/settings"
                >
                    <Image
                        aria-hidden
                        src="/window.svg"
                        alt="Window icon"
                        width={16}
                        height={16}
                    />
                    Settings
                </Link>
                <Link
                    className="flex items-center gap-2 hover:underline hover:underline-offset-4"
                    href="/"
                >
                    <Image
                        aria-hidden
                        src="/globe.svg"
                        alt="Globe icon"
                        width={16}
                        height={16}
                    />
                    Projects
                </Link>
            </footer>
        </div>
        </body>
        </html>
    );
}
