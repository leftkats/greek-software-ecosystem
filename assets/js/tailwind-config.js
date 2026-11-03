tailwind.config = {
    darkMode: "class",
    theme: {
        extend: {
            colors: {
                surface: "#f8fafc",
                "surface-dark": "#0b1220",
            },
            fontFamily: {
                display: ["Inter", "sans-serif"],
                mono: ["JetBrains Mono", "monospace"],
            },
            boxShadow: {
                soft: "0 10px 30px rgba(2, 6, 23, 0.08)",
                "soft-dark": "0 10px 30px rgba(0, 0, 0, 0.3)",
            },
        },
    },
};
