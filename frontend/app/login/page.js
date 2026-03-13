import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { signSession } from '@/lib/session';

export const metadata = { title: "Login - Personal Agent" };

function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string") {
    return false;
  }
  let mismatch = a.length === b.length ? 0 : 1;
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i += 1) {
    const charA = i < a.length ? a.charCodeAt(i) : 0;
    const charB = i < b.length ? b.charCodeAt(i) : 0;
    mismatch |= charA ^ charB;
  }
  return mismatch === 0;
}

async function hashPassword(password) {
  const encoder = new TextEncoder();
  const data = encoder.encode(password);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, "0")).join("");
}

export default async function LoginPage({ searchParams }) {
  const sp = await Promise.resolve(searchParams);
  const error = sp?.error;

  const errorMapping = {
    "invalid_credentials": "The username or password you entered is incorrect.",
    "invalid_request": "Invalid request format.",
  };
  const errorMessage = error ? (errorMapping[error] || "An error occurred during sign in.") : null;

  async function handleLogin(formData) {
    "use server";
    
    const username = formData.get("username");
    const password = formData.get("password");

    if (typeof username !== "string" || typeof password !== "string") {
      redirect("/login?error=invalid_request");
    }

    const hashedPassword = await hashPassword(password);
    
    const authUsersStr = process.env.AUTH_USERS || "";
    const users = authUsersStr.split(",").map(u => u.trim()).filter(Boolean);
    
    let isValid = false;
    for (const userConfig of users) {
      const firstColonIdx = userConfig.indexOf(":");
      if (firstColonIdx === -1) {
        continue;
      }
      const u = userConfig.slice(0, firstColonIdx);
      const p = userConfig.slice(firstColonIdx + 1);
      
      const isUsernameMatch = timingSafeEqual(u, username);
      const isPasswordMatch = timingSafeEqual(p, hashedPassword);
      
      if (isUsernameMatch && isPasswordMatch) {
        isValid = true;
      }
    }
    
    if (process.env.NODE_ENV === "development" && users.length === 0 && process.env.ALLOW_EMPTY_AUTH === "true") {
      isValid = true;
    }
    
    if (isValid) {
      const expiresAt = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000); // 30 days
      const token = await signSession({ username, exp: expiresAt.getTime() });
      
      const cookieStore = await cookies();
      cookieStore.set("pa_session", token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        expires: expiresAt,
        path: "/",
        sameSite: "lax",
      });
      
      redirect("/");
    } else {
      redirect("/login?error=invalid_credentials");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-xl shadow-sm border border-gray-200">
        <div>
          <h2 className="mt-2 text-center text-3xl font-extrabold text-gray-900">
            Personal Agent
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Sign in to your account
          </p>
        </div>
        
        {errorMessage && (
          <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded text-sm text-center">
            {errorMessage}
          </div>
        )}

        <form className="mt-8 space-y-6" action={handleLogin}>
          <div className="rounded-md shadow-sm space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700">Username</label>
              <input
                id="username"
                name="username"
                type="text"
                required
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 rounded-md placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">Password</label>
              <input
                id="password"
                name="password"
                type="password"
                required
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 rounded-md placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              />
            </div>
          </div>

          <div>
            <button
              type="submit"
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
            >
              Sign in
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
