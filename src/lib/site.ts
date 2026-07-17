export const site = {
  name: 'Allentronics',
  domain: 'allentronics.com.au',
  url: 'https://allentronics.com.au',
  email: 'info@allentronics.com',
  phone: '0447 238 034',
  phoneHref: 'tel:+61447238034',
  socials: [
    { label: 'Instagram', href: 'https://instagram.com/allentronics' },
    { label: 'LinkedIn', href: 'https://linkedin.com/company/allentronics' },
  ],
};

export const nav = [
  { label: 'Home', href: '/' },
  { label: 'Manufacturing', href: '/manufacturing/' },
  {
    label: 'Education',
    href: '/education/3d-printing-cad/',
    children: [
      { label: '3D Printing & CAD', href: '/education/3d-printing-cad/' },
      { label: 'Machine Leasing', href: '/education/machine-leasing/' },
      { label: 'AI Tools in Education', href: '/education/ai-tools-in-education/' },
      { label: 'Micro:bits & Electronics', href: '/education/microbits-electronics/' },
    ],
  },
  { label: 'Contact', href: '/contact/' },
];

export const primaryCta = { label: 'Discuss a program', href: '/contact/' };
