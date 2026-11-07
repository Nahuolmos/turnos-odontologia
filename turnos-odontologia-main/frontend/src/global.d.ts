/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_FRONTEND_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module '*.css' {
  const content: { [className: string]: string };
  export default content;
}

declare namespace Vi {
  interface JestAssertion<T = any> extends jest.Matchers<void, T> {}
}

declare namespace vitest {
  interface Assertion<T = any> extends jest.Matchers<void, T> {}
}

declare module 'vitest' {
  interface Assertion<T = any> extends jest.Matchers<void, T> {}
}