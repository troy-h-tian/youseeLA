/** Display-only images hosted by the businesses. Separate from model evidence and pipeline exports. */
export interface BusinessPhoto {
  url: string;
  alt: string;
  caption: string;
  sourceUrl: string;
}

export const BUSINESS_PHOTOS: Record<string, BusinessPhoto> = {
  'dulans-manchester': {
    url: 'https://irp.cdn-website.com/e6295603/dms3rep/multi/opt/Dulans-Manch-Dining-1920w.jpg',
    alt: "Dining area at Dulan's Soul Food Kitchen on Manchester Boulevard",
    caption: 'Manchester Boulevard dining room',
    sourceUrl: 'https://www.dulans-sfk.com/',
  },
  'hilltop-inglewood': {
    url: 'https://images.squarespace-cdn.com/content/v1/5a847759e45a7c9c4931b0d6/1629908129577-YWS96IUBO6OG438P2LWA/Inglewood+exterior.jpg?format=750w',
    alt: 'Exterior of Hilltop Coffee + Kitchen in Inglewood',
    caption: 'Inglewood storefront',
    sourceUrl: 'https://www.findyourhilltop.com/inglewood',
  },
  'serving-spoon': {
    url: 'https://www.theservingspoon.net/_astro/exterior-storefront.CKk_tVqj_ZOcXIO.webp',
    alt: 'The Serving Spoon storefront and parking lot on Centinela Avenue',
    caption: 'Centinela Avenue storefront',
    sourceUrl: 'https://www.theservingspoon.net/visit/',
  },
  'sweet-red-peach': {
    url: 'https://images.getbento.com/accounts/06e157603cbe7b2083709b893df763ee/media/images/72559Sweet_Red_Peach.jpg?w=750&fit=max&auto=compress,format',
    alt: 'Blue cupcake with white frosting, pictured on Sweet Red Peach’s website',
    caption: 'Illustrative dessert photo',
    sourceUrl: 'https://www.sweetredpeach.com/',
  },
  'toast-and-jam': {
    url: 'https://images.getbento.com/accounts/10b888c21c033152e2dcddc1e80c8a76/media/images/91505Assortment_4.TTJ.jpg?w=750&fit=max&auto=compress,format',
    alt: 'Breakfast dishes from The Toast & Jam',
    caption: 'Food from The Toast & Jam',
    sourceUrl: 'https://www.thetoastandjam.com/',
  },
};
