import type {Metadata} from "next";
import Image from "next/image";
import Link from "next/link";
import {Geist, Geist_Mono} from "next/font/google";
import "./globals.css";
import React from "react";
import AIThinking from "@components/AIThinking";

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

// Reusable links array
const navLinks = [
    {
        href: "/create",
        icon: "/file.svg",
        alt: "File icon",
        label: "New",
    },
    {
        href: "/settings",
        icon: "/window.svg",
        alt: "Window icon",
        label: "Settings",
    },
    {
        href: "/",
        icon: "/globe.svg",
        alt: "Globe icon",
        label: "Projects",
    },
];

// NavLinks component
const NavLinks = () => (
    <div className="flex gap-6">
        {navLinks.map((link) => (
            <Link
                key={link.href}
                className="flex items-center gap-2 hover:underline hover:underline-offset-4"
                href={link.href}
            >
                <Image
                    aria-hidden
                    src={link.icon}
                    alt={link.alt}
                    width={16}
                    height={16}
                />
                {link.label}
            </Link>
        ))}
    </div>
);

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
            <header className="bg-gray-800 text-white py-4">
                <div className="container mx-auto flex justify-between items-center px-4">
                    {/* Site name on the left */}
                    <h1 className="text-lg font-bold">AI Text Corrector</h1>

                    {/* Centered navigation links */}
                    <div className="absolute left-1/2 transform -translate-x-1/2">
                        <NavLinks/>
                    </div>

                    {/* AIThinking indicator on the right */}
                    <AIThinking/>
                </div>
            </header>

            {/* Main Content */}
            <main className="py-10 flex-grow flex flex-col items-center">
                <div className="w-full flex-grow flex flex-col items-center px-4">
                    {children}
                </div>
            </main>

            {/* Footer */}
            <footer className="bg-gray-800 text-white py-4 flex justify-center">
                <NavLinks/> {/* Footer nav links */}
            </footer>
        </div>
        </body>
        </html>
    );
}
