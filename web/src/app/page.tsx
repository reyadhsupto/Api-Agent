import { redirect } from 'next/navigation';

/** Send the site root to the authenticated workspace home screen. */
export default function RootPage(): never {
  redirect('/workspace');
}
