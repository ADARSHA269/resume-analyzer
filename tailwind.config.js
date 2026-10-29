/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#17211d',
        muted: '#77827c',
        canvas: '#f6f7f5',
        green: '#39765b',
      },
    },
  },
  plugins: [],
};
