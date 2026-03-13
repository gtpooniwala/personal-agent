import { signIn } from "@/auth";

export const metadata = { title: "Login - Personal Agent" };

export default async function LoginPage({ searchParams }) {
  const sp = await Promise.resolve(searchParams);
  const error = sp?.error;

  const errorMapping = {
    AccessDenied: "Access denied. Your Google account is not authorised.",
    OAuthSignin: "Could not initiate Google sign in. Please try again.",
    OAuthCallback: "Error during Google sign in. Please try again.",
    OAuthCallbackError: "Error during Google sign in. Please try again.",
  };
  const errorMessage = error
    ? (errorMapping[error] ?? "An error occurred during sign in.")
    : null;

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

        <form
          action={async () => {
            "use server";
            await signIn("google", { redirectTo: "/" });
          }}
        >
          <button
            type="submit"
            className="group relative w-full flex justify-center py-2 px-4 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
          >
            Sign in with Google
          </button>
        </form>
      </div>
    </div>
  );
}
