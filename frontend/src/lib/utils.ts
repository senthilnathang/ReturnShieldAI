import { type ClassValue, clsx } from 'clsx';
import { extendTailwindMerge } from 'tailwind-merge';

const twMerge = extendTailwindMerge({
  override: {
    classGroups: {
      'font-size': [
        'text-2xl',
        'text-l',
        'text-m',
        'text-s',
        'text-r',
        'text-xs',
        'text-2xs',
        'text-h1',
        'text-h2',
        'text-default',
        'text-small',
        'text-tiny',
      ],
    },
  },
  extend: {
    classGroups: {
      p: ['p-3xl', 'p-2xl', 'p-xl', 'p-lg', 'p-md', 'p-sm', 'p-xs', 'p-2xs'],
    },
  },
});

export const cn = (...classLists: ClassValue[]) => twMerge(clsx(classLists));
