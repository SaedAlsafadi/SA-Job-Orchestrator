import { create } from "zustand";
import api from "@/services/api";

export interface CandidateProfile {
  id: string;
  version: number;
  identity: { first_name: string; last_name: string; email: string; phone: string };
  location: { country: string; city: string; preferred_locations: string[]; willing_to_relocate: boolean; remote_preference: string };
  employment: { current_title: string; years_of_experience: number; notice_period: string };
  work_authorization: { nationality: string; residency_country: string; work_authorization_status: string; iqama_transferable: boolean };
  education: Array<any>;
  experience: Array<any>;
  skills: Array<any>;
  projects: Array<any>;
  certifications: Array<any>;
  preferences: any;
}

interface ProfileState {
  profile: CandidateProfile | null;
  isLoading: boolean;
  error: string | null;
  fetchProfile: () => Promise<void>;
  updateProfile: (data: Partial<CandidateProfile>) => Promise<void>;
}

export const useProfileStore = create<ProfileState>((set) => ({
  profile: null,
  isLoading: false,
  error: null,

  fetchProfile: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get("/candidate-profile");
      set({ profile: response.data.id === "none" ? null : response.data, isLoading: false });
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
    }
  },

  updateProfile: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.post("/candidate-profile", data);
      set({ profile: response.data, isLoading: false });
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
    }
  },
}));
